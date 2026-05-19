# Auditoria De Componente: Dash Attack V2

## Alcance

Esta auditoria corrige solo el componente `dash_attack`. No se refactorizaron las demas animaciones.

## Problema Detectado

El `dash_attack` anterior no estaba tan roto como `air_attack`, pero seguia siendo un draft tecnico:

- escala variable entre frames,
- lectura de accion irregular,
- cierre de animacion poco claro,
- sin componente canonico dedicado,
- dependiente del atlas global de combate.

## Correccion

Se genero una tira dedicada de 8 frames para `dash_attack`, se removio chroma a alpha y se normalizo el componente en dos salidas:

- Canonica high-res: `384x256`
- Compatibilidad legacy: `192x192`

## Recursos

| Recurso | Ruta |
| --- | --- |
| Frames canonicos | `art/characters/astra-mycelion/game-ready/components/dash_attack/frames/` |
| Atlas canonico | `art/characters/astra-mycelion/game-ready/components/dash_attack/atlas/astra_mycelion_dash_attack_v2_atlas.png` |
| Metadata canonica | `art/characters/astra-mycelion/game-ready/components/dash_attack/metadata/dash_attack_component.json` |
| Contact sheet QA high-res | `art/characters/astra-mycelion/game-ready/qa/dash_attack/dash_attack_v2_contact_hi.png` |
| Contact sheet QA legacy | `art/characters/astra-mycelion/game-ready/qa/dash_attack/dash_attack_v2_contact_legacy.png` |
| Frames legacy reemplazados | `art/characters/astra-mycelion/game-ready/frames/combat-defense/dash_attack/` |

## QA

Estado: `passes-component-audit`

Checks:

- 8 frames legibles.
- Ningun frame toca bordes.
- Sin fragmentos de sprites vecinos.
- PNG con alpha real.
- Atlas canonico dedicado.
- Metadata actualizada para `dash_attack`.

## Nota

El atlas global de combate aun contiene otros componentes no auditados. En esta oleada solo se corrigio `dash_attack`, siguiendo el proceso por cascada.
