"""Platform for light integration."""
from __future__ import annotations

import logging
from datetime import timedelta

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            COLOR_MODE_BRIGHTNESS,
                                            COLOR_MODE_ONOFF, PLATFORM_SCHEMA,
                                            LightEntity)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import hubspace as hs

SCAN_INTERVAL = timedelta(seconds=60)
BASE_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

CONF_FRIENDLYNAMES: Final = "friendlynames"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Required(CONF_FRIENDLYNAMES, default=[]): vol.All(cv.ensure_list, [cv.string]),
})


def _brightness_to_hass(value):
    return int(value) * 255 // 100


def _brightness_to_hubspace(value):
    return value * 100 // 255


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Awesome Light platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.

    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    refresh_token = hs.getRefreshCode(username, password)
    accountId = hs.getAccountId(refresh_token)

    entities = []

    for friendlyname in config.get(CONF_FRIENDLYNAMES):
        childId, model = hs.getChildId(refresh_token, accountId, friendlyname)
        entities.append(HubspaceLight(username, password,
                        friendlyname, childId, model))
        if model == 'HB-200-1215WIFIB':
            for instance in ['zone-1', 'zone-2', 'zone-3']:
                entities.append(HubspaceLight(
                    username, password, friendlyname+' '+instance, childId, model, 'toggle', instance))

    #entities = [HubspaceLight(username, password, friendlyname) for friendlyname in config.get(CONF_FRIENDLYNAMES)]
    if not entities:
        return
    add_entities(entities, True)
    # Setup connection with devices/cloud


class HubspaceLight(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(self, username, password, friendlyname, childId, model, powerStateName='power', instance=None) -> None:
        """Initialize an AwesomeLight."""
        self._username = username
        self._password = password
        self._name = friendlyname
        self._refresh_token = None
        self._accountId = None
        self._state = 'off'
        self._powerStateName = powerStateName
        self._instance = instance
        self._childId = None
        self._model = None
        self._brightness = None
        self._useBrightness = False
        self._childId = childId
        self._model = model

        self._refresh_token = hs.getRefreshCode(self._username, self._password)
        self._accountId = hs.getAccountId(self._refresh_token)

        # https://www.homedepot.com/p/Commercial-Electric-500-Watt-Single-Pole-Smart-Hubspace-Dimmer-with-Motion-Sensor-White-HPDA311CWB/317249353
        if self._model == 'HPDA311CWB':
            self._useBrightness = True

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def supported_color_modes(self) -> set[str] or None:
        """Flag supported color modes."""
        if self._useBrightness:
            return {COLOR_MODE_BRIGHTNESS}
        else:
            return {COLOR_MODE_ONOFF}

    @property
    def brightness(self) -> int or None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state == 'on'

    def turn_on(self, **kwargs: Any) -> None:
        state = hs.setState(self._refresh_token, self._accountId,
                            self._childId, self._powerStateName, "on", self._instance)
        if self._useBrightness:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
            hs.setState(self._refresh_token, self._accountId, self._childId,
                        "brightness", _brightness_to_hubspace(brightness))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr["model"] = self._model
        return attr

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        state = hs.setState(self._refresh_token, self._accountId,
                            self._childId, self._powerStateName, "off", self._instance)

    @property
    def should_poll(self):
        """Turn on polling """
        return True

    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = hs.getState(self._refresh_token, self._accountId,
                                  self._childId, self._powerStateName, self._instance)

        if self._useBrightness:
            self._brightness = _brightness_to_hass(hs.getState(
                self._refresh_token, self._accountId, self._childId, "brightness", self._instance))
