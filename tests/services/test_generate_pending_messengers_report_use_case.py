import unittest
from unittest.mock import MagicMock
from src.services.generate_pending_messengers_report_use_case import GeneratePendingMessengersReportUseCase
from src.domain.exceptions import NoDataFoundError, ReportGenerationError
from src.domain.messenger import MessengerContact

class TestGeneratePendingMessengersReportUseCase(unittest.TestCase):

    def test_generate_report_success(self):
        """Caso de éxito: se consultan y mapean datos, y se genera un PDF."""
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_pending_messengers_data.return_value = [
            {"name": "Juan Perez", "phone": "1234567890", "pending_count": 5},
            {"name": "Maria Lopez", "phone": "0987654321", "pending_count": 3}
        ]

        mock_pdf_provider = MagicMock()
        mock_pdf_provider.generate_pending_messengers_report.return_value = b"%PDF-1.4 mock_bytes"

        use_case = GeneratePendingMessengersReportUseCase(mock_repo, mock_pdf_provider)
        criteria = {"networkCode": "1009"}

        # Act
        result = use_case.execute(criteria)

        # Assert
        self.assertEqual(result, b"%PDF-1.4 mock_bytes")
        mock_repo.get_pending_messengers_data.assert_called_once_with(criteria)
        mock_pdf_provider.generate_pending_messengers_report.assert_called_once()
        
        # Validar mapeo correcto
        messengers = mock_pdf_provider.generate_pending_messengers_report.call_args[0][0]
        self.assertEqual(len(messengers), 2)
        self.assertIsInstance(messengers[0], MessengerContact)
        self.assertEqual(messengers[0].name, "Juan Perez")
        self.assertEqual(messengers[0].phone, "1234567890")
        self.assertEqual(messengers[0].pending_count, 5)

    def test_generate_report_no_data(self):
        """Caso de fallo: no hay datos del repositorio, lanza NoDataFoundError."""
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_pending_messengers_data.return_value = []

        mock_pdf_provider = MagicMock()

        use_case = GeneratePendingMessengersReportUseCase(mock_repo, mock_pdf_provider)

        # Act & Assert
        with self.assertRaisesRegex(NoDataFoundError, "No hay mensajeros pendientes"):
            use_case.execute({"networkCode": "1009"})

    def test_generate_report_generation_error(self):
        """Caso de fallo: falla la librería PDF, lanza ReportGenerationError."""
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_pending_messengers_data.return_value = [
            {"name": "Juan Perez", "phone": "1234567890", "pending_count": 5}
        ]

        mock_pdf_provider = MagicMock()
        mock_pdf_provider.generate_pending_messengers_report.side_effect = Exception("Falla de fpdf")

        use_case = GeneratePendingMessengersReportUseCase(mock_repo, mock_pdf_provider)

        # Act & Assert
        with self.assertRaisesRegex(ReportGenerationError, "Error al generar el PDF"):
            use_case.execute({"networkCode": "1009"})

if __name__ == '__main__':
    unittest.main()
