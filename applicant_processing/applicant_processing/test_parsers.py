# Copyright (c) 2026, Admin and contributors
# Test suite for Passport MRZ-Targeted OCR + Checksum Decoder and PyMuPDF Contract Structurizer

import unittest
from applicant_processing.applicant_processing.utils.passport_mrz import (
    compute_icao_checksum,
    verify_and_correct_checksum,
    parse_mrz_td3,
    parse_mrz_td1,
    extract_mrz_from_raw_text
)
from applicant_processing.applicant_processing.utils.contract_parser import (
    ContractTextStructurizer,
    parse_structured_contract_text
)

class TestPassportMRZ(unittest.TestCase):
    def test_icao_checksum_computation(self):
        # Standard ICAO 9303 test vector: "L8988901C" -> check digit is 4
        # L (21)*7 + 8*3 + 9*1 + 8*7 + 8*3 + 9*1 + 0*7 + 1*3 + C (12)*1
        # = 147 + 24 + 9 + 56 + 24 + 9 + 0 + 3 + 12 = 284 % 10 = 4
        chk = compute_icao_checksum("L8988901C")
        self.assertEqual(chk, 4)

    def test_td3_mrz_parsing_and_checksum_validation(self):
        line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
        line2 = "L8988901C4UTO6908061F9406236ZE184226B<<<<<10"
        
        parsed = parse_mrz_td3(line1, line2)
        self.assertEqual(parsed["passport_number"], "L8988901C")
        self.assertEqual(parsed["first_name"], "Anna")
        self.assertEqual(parsed["middle_name"], "Maria")
        self.assertEqual(parsed["last_name"], "Eriksson")
        self.assertEqual(parsed["gender"], "Female")
        self.assertEqual(parsed["date_of_birth"], "1969-08-06")
        self.assertEqual(parsed["passport_expiry"], "1994-06-23")
        self.assertTrue(parsed["checksum_validation"]["passport_number"]["valid"])
        self.assertTrue(parsed["checksum_validation"]["date_of_birth"]["valid"])
        self.assertTrue(parsed["checksum_validation"]["expiry_date"]["valid"])

    def test_ethiopian_passport_mrz_parsing(self):
        line1 = "PQETHWACHAMO<<ASNEKECH<TEDESSE<<<<<<<<<<<<<<<<"
        line2 = "EQ25760963ETH0012027F30051210<<<<<<<<<<<<<<04"
        
        parsed = parse_mrz_td3(line1, line2)
        self.assertEqual(parsed["passport_number"], "EQ2576096")
        self.assertEqual(parsed["first_name"], "Asnekech")
        self.assertEqual(parsed["middle_name"], "Tedesse")
        self.assertEqual(parsed["last_name"], "Wachamo")
        self.assertEqual(parsed["full_name"], "Asnekech Tedesse Wachamo")
        self.assertEqual(parsed["nationality"], "Ethiopia")
        self.assertEqual(parsed["gender"], "Female")
        self.assertEqual(parsed["date_of_birth"], "2000-12-02")
        self.assertEqual(parsed["passport_expiry"], "2030-05-12")
        self.assertTrue(parsed["checksum_validation"]["passport_number"]["valid"])
        self.assertTrue(parsed["checksum_validation"]["date_of_birth"]["valid"])
        self.assertTrue(parsed["checksum_validation"]["expiry_date"]["valid"])

    def test_checksum_self_correction(self):
        # Test case where OCR misidentified '0' as 'O' or '1' as 'I'
        # Correct: 9805141 (DOB 14 May 1998 with check digit 1)
        raw_dob_with_ocr_error = "98O514"
        val, corr, chk = verify_and_correct_checksum(raw_dob_with_ocr_error, "1", is_numeric=True)
        self.assertTrue(val)
        self.assertEqual(corr, "980514")



class TestContractStructurizer(unittest.TestCase):
    def test_multiline_text_unification(self):
        raw_contract_text = """
Contract Number: CONT-98765432
Visa Number: 1309827465

Under Employer
Name: ABDULLAH MOHAMMED
AL-OTAIBI
National ID Number: 1098765432
Street: King Fahd Road,
Al Malaz District
City: Riyadh
Mobile: +966501234567
Telephone: +966114567890

Under Recruiting agency
Name: Al Qurashi Recruitment
Office Co.
License No: REC-7788
Telephone: +966501234567
Street: Olaya Main Street
City: Riyadh
Email: info@alqurashirecruitment.com

Under Her Country Recruitment Agency
Name: ANWAR SULTAN FOREIGN
EMPLOYMENT AGENT
License No: 3226
Street: Bole Road,
Addis Ababa
City: Addis Ababa
Contact No: +251911223344
Email: info@anwarsultanagency.com
"""
        parsed = parse_structured_contract_text(raw_contract_text)
        
        self.assertEqual(parsed["contract_number"], "CONT-98765432")
        self.assertEqual(parsed["visa_number"], "1309827465")
        self.assertIn("ABDULLAH MOHAMMED", parsed["employer_name"])
        self.assertEqual(parsed["employer_id"], "1098765432")
        self.assertEqual(parsed["employer_city"], "Riyadh")
        self.assertEqual(parsed["employer_mobile"], "+966501234567")
        
        self.assertIn("Al Qurashi", parsed["recruiting_agency_name"])
        self.assertEqual(parsed["recruiting_agency_license"], "REC-7788")
        
        self.assertIn("ANWAR SULTAN", parsed["origin_agency_name"])
        self.assertEqual(parsed["origin_agency_license"], "3226")
        self.assertEqual(parsed["origin_agency_city"], "Addis Ababa")
        self.assertEqual(parsed["origin_agency_phone"], "+251911223344")

if __name__ == "__main__":
    unittest.main()
