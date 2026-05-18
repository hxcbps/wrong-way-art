# Wrong Way Art Repository

Repositorio de arte para el videojuego 2D donde lo logico es ilogico y lo ilogico es el camino.

## Protagonista

Nombre de produccion: **Astra Mycelion**

Astra Mycelion es un guardian bio-cyber ilogico construido con vidrio obsidiana, circuitos de micelio vivo, fragmentos ceramicos flotantes y energia ambar. La silueta evita mascaras con cuernos, ojos ovalados, armaduras azules o formas reconocibles de otros personajes.

## Estructura

- `art/characters/astra-mycelion/`: recursos del protagonista.
- `art/vfx/`: efectos visuales separados.
- `art/world/`: tiles, props y escenarios.
- `art/ui/`: HUD, iconos y menus.
- `docs/`: biblia visual, plan de animacion y reglas de produccion.
- `manifests/`: indice de assets.
- `tools/`: scripts reproducibles para cortar, normalizar y empaquetar assets.

## Build De Assets

```bash
python3 tools/build_astra_mycelion_gameplay_assets.py
python3 tools/build_astra_mycelion_secondary_assets.py
```

Las salidas listas para integracion viven en:

`art/characters/astra-mycelion/game-ready/`

## Regla creativa

Lo ilogico no es un efecto decorativo: es la regla del mundo. Las animaciones deben comunicar que romper la logica fisica es la forma correcta de avanzar.
