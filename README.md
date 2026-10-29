# Salus iT500 (Asíncrono) para Home Assistant

Integración custom para Home Assistant que permite controlar un termostato
**Salus iT500** a través de la nube de la app oficial, usando `aiohttp`
de forma totalmente asíncrona (sin bloquear el event loop de HA).

> ⚠️ Integración no oficial, sin relación con Salus/Computime.
>
> **Desde la v2.0** usa la nube de la app Android *iT500 Plus*
> (`com.saluscontrols.it500v2`, API de Arrayent), porque el portal
> `salus-it500.com` dejó de responder en octubre de 2026. Es una API no
> documentada: puede cambiar sin aviso.

## Características

- Configuración desde la interfaz de HA (`config_flow`), sin YAML; el
  termostato se descubre solo a partir de tu cuenta.
- Dos **zonas de calefacción**. La zona de **agua caliente** no está
  implementada.
- Modos por zona: `OFF`, `AUTO` (incluye "hold" temporal, visible en el
  atributo `hold`) y `HEAT` (manual).
- Temperatura actual y consigna; ajuste de consigna por zona.
- Interruptor maestro para apagar/poner en AUTO ambas zonas.
- Temperatura antihielo (`number`, valor en centésimas de grado).
- Los cambios esperan la **confirmación real** del termostato (suele tardar
  unos 10 s) y, si el servidor ignora la orden, HA muestra un error en vez
  de aparentar que funcionó.
- Datos cada 30 s con `DataUpdateCoordinator`.

## Limitaciones conocidas

- No se procesan los horarios/programaciones.
- Hace falta la **apikey de la app** (ver más abajo).

## Instalación

### Vía HACS (repositorio custom)

1. HACS → Integraciones → menú (⋮) → **Repositorios personalizados**.
2. Añade la URL de este repositorio con categoría **Integración**.
3. Busca "Salus iT500" en HACS e instala.
4. Reinicia Home Assistant.

### Manual

1. Copia la carpeta `custom_components/salus_it500` dentro de
   `<config>/custom_components/` de tu instalación de Home Assistant.
2. Reinicia Home Assistant.

## Configuración

1. **Ajustes → Dispositivos y servicios → Añadir integración** → "Salus iT500".
2. Introduce el **usuario** y **contraseña** de tu cuenta de la app iT500
   Plus y la **apikey de la app**.

### ¿De dónde sale la apikey?

La apikey identifica a la *aplicación* (no a ti) y **no se publica en este
repositorio**. Cada usuario debe obtenerla de su propia copia de la app
oficial (por ejemplo, inspeccionando el APK que ya tiene instalado). No la
compartas públicamente.

### Si ya tenías la versión 1.x

Home Assistant te pedirá reautenticar: introduce usuario, contraseña y
apikey. Las entidades y su historial se conservan.

## Entidades creadas

| Entidad | Dominio | Descripción |
|---|---|---|
| `climate.salus_zona_1` / `climate.salus_zona_2` | `climate` | Control de cada zona |
| `number.salus_frost_temp` | `number` | Temperatura antihielo |
| `switch.salus_master_switch` | `switch` | Encendido/apagado global |

## Desarrollo

`custom_components/salus_it500/client.py` es el cliente de la API, sin
dependencias de Home Assistant. Pruebas: `pytest tests`. Para comprobar
contra tu termostato (solo lectura por defecto):
`SALUS_USER`, `SALUS_PASS`, `SALUS_API_KEY` y `python scripts/live_check.py`.

## Créditos y referencias

El cliente de la API es una implementación propia, escrita analizando
el tráfico y el comportamiento de la app oficial, pero el diseño general de esta integración se ha
inspirado en desarrollos previos de la comunidad de Home Assistant para
este mismo dispositivo:

- [floringhimie/salusfy](https://github.com/floringhimie/salusfy) — primer
  custom component conocido para el Salus iT500 en Home Assistant.
- [RichyA/pyit500](https://github.com/RichyA/pyit500) — librería Python
  para la API del iT500, usada como referencia de partida.

## Licencia

MIT — ver [LICENSE](LICENSE).
