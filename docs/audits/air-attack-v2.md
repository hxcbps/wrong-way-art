# Auditoria De Componente: Air Attack V2

## Alcance

Esta auditoria corrige solo el componente `air_attack`. No se refactorizaron las demas animaciones.

## Problema Detectado

Los frames anteriores de `air_attack` venian de una hoja global con grilla irregular. El resultado fue:

- sprites cortados por la mitad,
- fragmentos de frames vecinos,
- pivots inconsistentes,
- atlas de combate contaminado en los slots de `air_attack`.

## Correccion

Se genero una tira dedicada de 6 frames para `air_attack`, se removio chroma a alpha y se normalizo el componente en dos salidas:

- Canonica high-res: `384x256`
- Compatibilidad legacy: `192x192`

## Recursos

| Recurso | Ruta |
| --- | --- |
| Frames canonicos | `art/characters/astra-mycelion/game-ready/components/air_attack/frames/` |
| Atlas canonico | `art/characters/astra-mycelion/game-ready/components/air_attack/atlas/astra_mycelion_air_attack_v2_atlas.png` |
| Metadata canonica | `art/characters/astra-mycelion/game-ready/components/air_attack/metadata/air_attack_component.json` |
| Contact sheet QA high-res | `art/characters/astra-mycelion/game-ready/qa/air_attack/air_attack_v2_contact_hi.png` |
| Contact sheet QA legacy | `art/characters/astra-mycelion/game-ready/qa/air_attack/air_attack_v2_contact_legacy.png` |
| Frames legacy reemplazados | `art/characters/astra-mycelion/game-ready/frames/combat-defense/air_attack/` |

## QA

Estado: `passes-component-audit`

Checks:

- 6 frames legibles.
- Ningun frame toca bordes.
- Sin fragmentos de sprites vecinos.
- PNG con alpha real.
- Atlas canonico dedicado.
- Metadata actualizada para `air_attack`.

## Nota

El atlas global de combate aun contiene otros componentes no auditados. En esta oleada solo se corrigio `air_attack`, siguiendo el proceso por cascada.
