"""Generate W3C WoT Thing Descriptions from device entries.

Routes to the correct provider-specific TD generator based on the
``provider`` field stored in each device definition.
"""

from providers import load_provider


def generate_td(device: dict, replay_base_url: str) -> dict:
    """Generate a WoT Thing Description for a device entry."""
    provider_name = device.get("provider")
    if provider_name is None:
        raise ValueError(
            f"Device {device.get('id', '?')} has no 'provider' field — "
            "cannot determine which TD generator to use"
        )
    provider = load_provider(provider_name)
    return provider.generate_td(device, replay_base_url)
