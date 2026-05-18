# Pipeline Gameplay-Ready

## Estado Actual

El build tecnico genera:

- 216 frames individuales normalizados a `192x192`.
- 3 atlas PNG: movement, combat/defense e illogical.
- Metadata JSON para animaciones, rectangulos de atlas, FPS, loop y pivots.
- Planes de importacion para Unity y Godot.
- Contact sheets QA para revisar consistencia visual.

## Comando

```bash
python3 tools/build_astra_mycelion_gameplay_assets.py
```

## Salidas

- `art/characters/astra-mycelion/game-ready/frames/`
- `art/characters/astra-mycelion/game-ready/atlases/`
- `art/characters/astra-mycelion/game-ready/metadata/`
- `art/characters/astra-mycelion/game-ready/qa/`

## Nota De QA

Las hojas base fueron generadas como arte draft y no como atlas tecnico perfecto. Algunas filas tienen mas o menos frames de los declarados, y algunas animaciones requieren refinamiento artistico final para evitar crops con fallback. El pipeline detecta y documenta esos casos en:

`art/characters/astra-mycelion/game-ready/metadata/astra_mycelion_animations.json`

La siguiente fase artistica debe producir hojas refinadas por animacion clave con grilla estricta: idle, run, jump, dash, attack, shield y teleport/glitch.
