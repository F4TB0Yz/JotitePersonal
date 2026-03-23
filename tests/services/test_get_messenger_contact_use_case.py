import pytest
from unittest.mock import create_autospec

from src.domain.messenger import MessengerContact, MessengerProfile, MessengerNotFoundException
from src.domain.interfaces.messenger_provider import IMessengerProvider
from src.services.get_messenger_contact_use_case import GetMessengerContactUseCase


class TestGetMessengerContactUseCase:

    def test_should_return_contact_from_profile_when_phone_is_available(self):
        """
        Escenario Happy Path 1: El mensajero es encontrado y su perfil tiene el teléfono directo.
        """
        # Arrange
        mock_provider = create_autospec(IMessengerProvider)
        use_case = GetMessengerContactUseCase(provider=mock_provider)
        
        name = "Juan Perez"
        network_code = "1009"
        profile_phone = "3001234567"
        
        profile = MessengerProfile(
            accountName="Juan Perez",
            accountCode="M001",
            customerNetworkName="Centro",
            accountPhone=profile_phone
        )
        # Seteamos el Mock para devolver la lista con el perfil
        mock_provider.search_messengers.return_value = [profile]

        # Act
        result = use_case.execute(name=name, network_code=network_code)

        # Assert
        assert isinstance(result, MessengerContact)
        assert result.name == "Juan Perez"
        assert result.phone == profile_phone
        assert result.accountCode == "M001"
        assert result.networkName == "Centro"
        
        mock_provider.search_messengers.assert_called_once_with(name.strip(), network_code)
        mock_provider.get_recent_waybill_no.assert_not_called()
        mock_provider.get_contact_from_tracking.assert_not_called()

    def test_should_fetch_waybill_and_track_when_no_phone_in_profile(self):
        """
        Escenario Fallback 1: El perfil no tiene teléfono, el Use Case obtiene una guía 
        reciente y extrae el teléfono del rastreo (tracking).
        """
        # Arrange
        mock_provider = create_autospec(IMessengerProvider)
        use_case = GetMessengerContactUseCase(provider=mock_provider)
        
        name = "Juan Perez"
        network_code = "1009"
        fallback_waybill_no = "JTC000123"
        tracking_phone = "3109876543"
        tracking_name = "Juan Perez Tracking"
        
        # Perfil sin teléfonos cargados
        profile = MessengerProfile(
            accountName="Juan Perez",
            accountCode="M001",
            customerNetworkCode="1009",
            customerNetworkName="Centro"
        )
        
        mock_provider.search_messengers.return_value = [profile]
        mock_provider.get_recent_waybill_no.return_value = fallback_waybill_no
        mock_provider.get_contact_from_tracking.return_value = (tracking_phone, tracking_name)

        # Act
        result = use_case.execute(name=name, network_code=network_code)

        # Assert
        assert isinstance(result, MessengerContact)
        assert result.name == tracking_name
        assert result.phone == tracking_phone
        assert result.accountCode == "M001"
        assert result.networkName == "Centro"
        
        mock_provider.search_messengers.assert_called_once()
        mock_provider.get_recent_waybill_no.assert_called_once_with("M001", "1009")
        mock_provider.get_contact_from_tracking.assert_called_once_with(fallback_waybill_no, name.lower())

    def test_should_propagate_messenger_not_found_exception_when_no_profiles_found(self):
        """
        Escenario Excepción 1: El provider no encuentra perfiles (Search vacío), 
        asegurando que el Use Case lance MessengerNotFoundException.
        """
        # Arrange
        mock_provider = create_autospec(IMessengerProvider)
        use_case = GetMessengerContactUseCase(provider=mock_provider)
        
        name = "Inexistente"
        # Search vacío
        mock_provider.search_messengers.return_value = [] 

        # Act & Assert
        with pytest.raises(MessengerNotFoundException, match="Mensajero no encontrado"):
            use_case.execute(name=name)

    def test_should_raise_value_error_when_name_is_empty(self):
        """
        El Use Case debe lanzar ValueError si se envía un nombre vacío o con espacios.
        """
        # Arrange
        mock_provider = create_autospec(IMessengerProvider)
        use_case = GetMessengerContactUseCase(provider=mock_provider)

        # Act & Assert
        with pytest.raises(ValueError, match="Nombre requerido"):
            use_case.execute(name="   ")

    def test_should_return_profile_without_phone_when_fallback_fails_but_profile_exists(self):
        """
        Si hay un perfil match pero no tiene teléfono, y no hay guías ni rastreo de fallback,
        se devuelve el contacto SIN teléfono pero CON datos del perfil.
        """
        # Arrange
        mock_provider = create_autospec(IMessengerProvider)
        use_case = GetMessengerContactUseCase(provider=mock_provider)
        
        name = "Juan Perez"
        
        profile = MessengerProfile(
            accountName="Juan Perez",
            accountCode="M001"
        )
        
        mock_provider.search_messengers.return_value = [profile]
        mock_provider.get_recent_waybill_no.return_value = None  # Fallback 1 falla

        # Act
        result = use_case.execute(name=name)

        # Assert
        assert isinstance(result, MessengerContact)
        assert result.name == "Juan Perez"
        assert result.phone is None
        assert result.accountCode == "M001"
