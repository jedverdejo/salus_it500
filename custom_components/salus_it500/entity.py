"""Base común de entidades."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Salusit500Coordinator


class SalusEntity(CoordinatorEntity[Salusit500Coordinator]):
    """Entidad ligada al termostato."""

    def __init__(self, coordinator: Salusit500Coordinator, uid: str, title: str) -> None:
        super().__init__(coordinator)
        self._uid = uid  # unique_id de la entrada: se conserva al migrar
        self._title = title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Salus",
            model="iT500",
            name=title,
        )

    @property
    def available(self) -> bool:
        return super().available and str(self.coordinator.data.get("online", "1")) != "0"
