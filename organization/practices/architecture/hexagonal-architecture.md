# Hexagonal architecture

- Model application-facing and infrastructure-facing boundaries as explicit ports.
- Keep domain behavior independent from transport and persistence adapters.
- Dependencies point inward; adapters implement ports owned by inner layers.
- Apply this practice only where the project explicitly enables it.
