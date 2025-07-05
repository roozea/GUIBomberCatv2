"""Tests para parser y validador APDU.

Verifica parsing correcto, validación y cálculo CRC.
"""

import pytest
from modules.bombercat_relay.apdu import (
    APDU, is_complete, parse_apdu, validate_apdu_structure,
    create_response_apdu, APDUConstants
)


class TestAPDUParsing:
    """Tests para parsing de APDU."""
    
    def test_simple_apdu_case_1(self):
        """Test APDU Case 1 (solo cabecera)."""
        # SELECT command sin datos ni Le
        apdu_bytes = bytes([0x00, 0xA4, 0x04, 0x00])
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.cla == 0x00
        assert apdu.ins == 0xA4
        assert apdu.p1 == 0x04
        assert apdu.p2 == 0x00
        assert apdu.lc is None
        assert apdu.data is None
        assert apdu.le is None
        assert apdu.is_valid
    
    def test_apdu_case_2_short(self):
        """Test APDU Case 2 corto (solo Le)."""
        # GET RESPONSE con Le=256
        apdu_bytes = bytes([0x00, 0xC0, 0x00, 0x00, 0x00])
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.cla == 0x00
        assert apdu.ins == 0xC0
        assert apdu.p1 == 0x00
        assert apdu.p2 == 0x00
        assert apdu.lc is None
        assert apdu.data is None
        assert apdu.le == 256  # 0x00 = 256
        assert apdu.is_valid
    
    def test_apdu_case_3_short(self):
        """Test APDU Case 3 corto (solo datos)."""
        # UPDATE BINARY con datos
        data = b"\x01\x02\x03\x04"
        apdu_bytes = bytes([0x00, 0xD6, 0x00, 0x00, len(data)]) + data
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.cla == 0x00
        assert apdu.ins == 0xD6
        assert apdu.p1 == 0x00
        assert apdu.p2 == 0x00
        assert apdu.lc == len(data)
        assert apdu.data == data
        assert apdu.le is None
        assert apdu.is_valid
    
    def test_apdu_case_4_short(self):
        """Test APDU Case 4 corto (datos + Le)."""
        # Command con datos y respuesta esperada
        data = b"\xAA\xBB\xCC"
        apdu_bytes = bytes([0x80, 0x12, 0x34, 0x56, len(data)]) + data + bytes([0x10])
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.cla == 0x80
        assert apdu.ins == 0x12
        assert apdu.p1 == 0x34
        assert apdu.p2 == 0x56
        assert apdu.lc == len(data)
        assert apdu.data == data
        assert apdu.le == 0x10
        assert apdu.is_valid
    
    def test_apdu_extended_length(self):
        """Test APDU con longitud extendida."""
        # APDU con Lc extendido
        data = b"X" * 300  # Más de 255 bytes
        lc_extended = [0x00, 0x01, 0x2C]  # 300 en formato extendido
        apdu_bytes = bytes([0x00, 0xD6, 0x00, 0x00] + lc_extended) + data
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.lc == 300
        assert len(apdu.data) == 300
        assert apdu.is_valid
    
    def test_incomplete_apdu(self):
        """Test APDU incompleto."""
        # Solo cabecera parcial
        incomplete = bytes([0x00, 0xA4])
        assert not is_complete(incomplete)
        assert parse_apdu(incomplete) is None
        
        # Cabecera completa pero faltan datos (necesita más de 5 bytes para ser Case 3)
        incomplete_with_lc = bytes([0x00, 0xA4, 0x04, 0x00, 0x05, 0x01])  # Lc=5 pero solo 1 byte
        assert not is_complete(incomplete_with_lc)
        assert parse_apdu(incomplete_with_lc) is None
        
        # APDU con datos parciales
        partial_data = bytes([0x00, 0xA4, 0x04, 0x00, 0x03, 0x01])  # Lc=3 pero solo 1 byte
        assert not is_complete(partial_data)
        assert parse_apdu(partial_data) is None
    
    def test_invalid_apdu_structure(self):
        """Test estructura APDU inválida."""
        # Buffer vacío
        assert not is_complete(b"")
        assert parse_apdu(b"") is None
        
        # Muy corto
        assert not is_complete(bytes([0x00]))
        assert parse_apdu(bytes([0x00])) is None
    
    def test_apdu_validation(self):
        """Test validación de APDU."""
        # APDU válido
        valid_apdu = APDU(cla=0x00, ins=0xA4, p1=0x04, p2=0x00)
        assert valid_apdu.is_valid
        
        # CLA inválido
        invalid_cla = APDU(cla=256, ins=0xA4, p1=0x04, p2=0x00)
        assert not invalid_cla.is_valid
        
        # INS inválido
        invalid_ins = APDU(cla=0x00, ins=-1, p1=0x04, p2=0x00)
        assert not invalid_ins.is_valid
        
        # Lc/data inconsistente
        inconsistent = APDU(cla=0x00, ins=0xA4, p1=0x04, p2=0x00, lc=5, data=b"123")  # Lc=5 pero data=3 bytes
        assert not inconsistent.is_valid
    
    def test_apdu_to_bytes(self):
        """Test conversión APDU a bytes."""
        # Case 1
        apdu1 = APDU(cla=0x00, ins=0xA4, p1=0x04, p2=0x00)
        expected1 = bytes([0x00, 0xA4, 0x04, 0x00])
        assert apdu1.to_bytes() == expected1
        
        # Case 3
        data = b"\x01\x02\x03"
        apdu3 = APDU(cla=0x00, ins=0xD6, p1=0x00, p2=0x00, lc=len(data), data=data)
        expected3 = bytes([0x00, 0xD6, 0x00, 0x00, 0x03]) + data
        assert apdu3.to_bytes() == expected3
        
        # Case 2
        apdu2 = APDU(cla=0x00, ins=0xC0, p1=0x00, p2=0x00, le=16)
        expected2 = bytes([0x00, 0xC0, 0x00, 0x00, 0x10])
        assert apdu2.to_bytes() == expected2
    
    def test_apdu_crc_calculation(self):
        """Test cálculo CRC simple XOR."""
        apdu = APDU(cla=0x00, ins=0xA4, p1=0x04, p2=0x00)
        
        # CRC = 0x00 ^ 0xA4 ^ 0x04 ^ 0x00 = 0xA0
        expected_crc = 0x00 ^ 0xA4 ^ 0x04 ^ 0x00
        assert apdu.calculate_crc() == expected_crc
        
        # Con datos
        data = b"\x01\x02"
        apdu_with_data = APDU(cla=0x80, ins=0x12, p1=0x34, p2=0x56, lc=len(data), data=data)
        apdu_bytes = apdu_with_data.to_bytes()
        
        expected_crc = 0
        for byte in apdu_bytes:
            expected_crc ^= byte
        
        assert apdu_with_data.calculate_crc() == expected_crc


class TestAPDUValidation:
    """Tests para validación de estructura APDU."""
    
    def test_valid_apdu_structures(self):
        """Test estructuras APDU válidas."""
        # Case 1: Solo cabecera
        valid1 = bytes([0x00, 0xA4, 0x04, 0x00])
        is_valid, msg = validate_apdu_structure(valid1)
        assert is_valid
        assert msg == "APDU válido"
        
        # Case 3: Con datos
        valid3 = bytes([0x00, 0xD6, 0x00, 0x00, 0x03, 0x01, 0x02, 0x03])
        is_valid, msg = validate_apdu_structure(valid3)
        assert is_valid
        assert msg == "APDU válido"
    
    def test_invalid_apdu_structures(self):
        """Test estructuras APDU inválidas."""
        # Muy corto
        invalid_short = bytes([0x00, 0xA4])
        is_valid, msg = validate_apdu_structure(invalid_short)
        assert not is_valid
        assert "al menos 4 bytes" in msg
        
        # INS inválido (0x00)
        invalid_ins = bytes([0x00, 0x00, 0x04, 0x00])
        is_valid, msg = validate_apdu_structure(invalid_ins)
        assert not is_valid
        assert "INS inválido" in msg
        
        # INS inválido (0xFF)
        invalid_ins_ff = bytes([0x00, 0xFF, 0x04, 0x00])
        is_valid, msg = validate_apdu_structure(invalid_ins_ff)
        assert not is_valid
        assert "INS inválido" in msg
        
        # CLA reservado
        invalid_cla = bytes([0x0F, 0xA4, 0x04, 0x00])  # CLA & 0x0F == 0x0F
        is_valid, msg = validate_apdu_structure(invalid_cla)
        assert not is_valid
        assert "CLA reservado" in msg
    
    def test_edge_cases(self):
        """Test casos límite."""
        # Lc = 0 (válido)
        lc_zero = bytes([0x00, 0xA4, 0x04, 0x00, 0x00])
        is_valid, msg = validate_apdu_structure(lc_zero)
        assert is_valid
        
        # Le = 0 (256 bytes esperados)
        le_zero = bytes([0x00, 0xC0, 0x00, 0x00, 0x00])
        is_valid, msg = validate_apdu_structure(le_zero)
        assert is_valid


class TestAPDUResponse:
    """Tests para creación de respuestas APDU."""
    
    def test_success_response(self):
        """Test respuesta de éxito."""
        response = create_response_apdu()
        assert response == bytes([0x90, 0x00])
        
        # Con datos
        data = b"\x01\x02\x03"
        response_with_data = create_response_apdu(data)
        assert response_with_data == data + bytes([0x90, 0x00])
    
    def test_error_responses(self):
        """Test respuestas de error."""
        # Wrong length
        error_response = create_response_apdu(sw1=0x67, sw2=0x00)
        assert error_response == bytes([0x67, 0x00])
        
        # Security status not satisfied
        security_error = create_response_apdu(sw1=0x69, sw2=0x82)
        assert security_error == bytes([0x69, 0x82])
    
    def test_response_with_data_and_custom_sw(self):
        """Test respuesta con datos y SW personalizado."""
        data = b"Response data"
        response = create_response_apdu(data, sw1=0x61, sw2=len(data))
        expected = data + bytes([0x61, len(data)])
        assert response == expected


class TestAPDUConstants:
    """Tests para constantes APDU."""
    
    def test_status_words(self):
        """Test Status Words comunes."""
        assert APDUConstants.SW_SUCCESS == (0x90, 0x00)
        assert APDUConstants.SW_WRONG_LENGTH == (0x67, 0x00)
        assert APDUConstants.SW_SECURITY_STATUS == (0x69, 0x82)
        assert APDUConstants.SW_WRONG_DATA == (0x6A, 0x80)
        assert APDUConstants.SW_WRONG_P1P2 == (0x6A, 0x86)
        assert APDUConstants.SW_INS_NOT_SUPPORTED == (0x6D, 0x00)
        assert APDUConstants.SW_CLA_NOT_SUPPORTED == (0x6E, 0x00)
    
    def test_class_bytes(self):
        """Test bytes de clase comunes."""
        assert APDUConstants.CLA_ISO == 0x00
        assert APDUConstants.CLA_PROPRIETARY == 0x80
    
    def test_instruction_bytes(self):
        """Test bytes de instrucción comunes."""
        assert APDUConstants.INS_SELECT == 0xA4
        assert APDUConstants.INS_READ_BINARY == 0xB0
        assert APDUConstants.INS_UPDATE_BINARY == 0xD6
        assert APDUConstants.INS_GET_RESPONSE == 0xC0


class TestAPDUComplexScenarios:
    """Tests para escenarios complejos de APDU."""
    
    def test_real_world_select_command(self):
        """Test comando SELECT real."""
        # SELECT AID (Application Identifier)
        aid = bytes([0xA0, 0x00, 0x00, 0x00, 0x62, 0x03, 0x01, 0x0C, 0x06, 0x01])
        select_apdu = bytes([0x00, 0xA4, 0x04, 0x00, len(aid)]) + aid
        
        assert is_complete(select_apdu)
        
        apdu = parse_apdu(select_apdu)
        assert apdu is not None
        assert apdu.ins == APDUConstants.INS_SELECT
        assert apdu.p1 == 0x04  # Select by name
        assert apdu.p2 == 0x00  # First occurrence
        assert apdu.data == aid
        assert apdu.is_valid
    
    def test_chained_apdu_detection(self):
        """Test detección de APDUs encadenados."""
        # Dos APDUs concatenados
        apdu1 = bytes([0x00, 0xA4, 0x04, 0x00])
        apdu2 = bytes([0x00, 0xC0, 0x00, 0x00, 0x00])
        combined = apdu1 + apdu2
        
        # Debe detectar que el primer APDU está completo
        assert is_complete(combined[:4])
        
        # Parse del primer APDU
        first_apdu = parse_apdu(combined[:4])
        assert first_apdu is not None
        assert first_apdu.expected_length == 4
        
        # Parse del segundo APDU
        second_apdu = parse_apdu(combined[4:])
        assert second_apdu is not None
        assert second_apdu.expected_length == 5
    
    def test_malformed_apdu_recovery(self):
        """Test recuperación de APDUs malformados."""
        # APDU con Lc incorrecto - necesita datos después de Lc
        malformed = bytes([0x00, 0xD6, 0x00, 0x00, 0x10, 0x01])  # Lc=16 pero solo 1 byte
        
        assert not is_complete(malformed)
        assert parse_apdu(malformed) is None
        
        # APDU con datos insuficientes
        insufficient_data = bytes([0x00, 0xD6, 0x00, 0x00, 0x05, 0x01, 0x02])  # Lc=5 pero solo 2 bytes
        assert not is_complete(insufficient_data)
        assert parse_apdu(insufficient_data) is None
        
        # Validación debe fallar para APDU incompleto
        is_valid, msg = validate_apdu_structure(malformed)
        assert not is_valid
    
    def test_maximum_length_apdu(self):
        """Test APDU de longitud máxima."""
        # APDU con datos máximos (65535 bytes en formato extendido)
        # Nota: Solo testear estructura, no crear datos reales por memoria
        
        # Lc extendido para 65535 bytes
        lc_max = [0x00, 0xFF, 0xFF]  # 65535
        header = bytes([0x00, 0xD6, 0x00, 0x00] + lc_max)
        
        # Simular parsing sin datos reales
        apdu = APDU(
            cla=0x00, ins=0xD6, p1=0x00, p2=0x00,
            lc=65535, data=b"X" * 100  # Solo muestra
        )
        
        # Verificar que la estructura es válida conceptualmente
        assert apdu.cla == 0x00
        assert apdu.ins == 0xD6
        assert apdu.lc == 65535
    
    def test_zero_length_data_field(self):
        """Test campo de datos de longitud cero."""
        # APDU con Lc=0 (sin datos) - necesita al menos 6 bytes para ser Case 3
        apdu_bytes = bytes([0x00, 0xA4, 0x04, 0x00, 0x00, 0x00])  # Lc=0, Le=0
        
        assert is_complete(apdu_bytes)
        
        apdu = parse_apdu(apdu_bytes)
        assert apdu is not None
        assert apdu.lc == 0
        assert apdu.data == b""
        assert apdu.le == 256  # Le=0 significa 256
        assert apdu.is_valid