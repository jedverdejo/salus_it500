# Salus iT500 (Asíncrono) para Home Assistant

Integración custom para Home Assistant que permite controlar un termostato
**Salus iT500** a través del portal cloud `salus-it500.com`, usando `aiohttp`
de forma totalmente asíncrona (sin bloquear el event loop de HA).

> ⚠️ Integración no oficial, sin relación con Salus/Computime. Depende del
> portal web `salus-it500.com`, no documentado públicamente, así que puede
> dejar de funcionar si Salus cambia su API.

## Características

- Configuración desde la interfaz de HA (`config_flow`), sin YAML.
- Dos zonas de climatización (`climate.CH1` / `climate.CH2`).
- Modos `OFF` / `AUTO` por zona.
- Lectura de temperatura actual y de consigna.
- Ajuste de temperatura objetivo por zona.
- Ajuste de temperatura antihielo (`number.frost_temp`).
- Interruptor maestro para apagar/encender ambas zonas a la vez (`switch`).
- Actualización de datos cada 60 s mediante `DataUpdateCoordinator`.

## Limitaciones conocidas

- **No se distingue el modo Manual del modo Auto**: la API de Salus no
  ofrece una forma fiable de diferenciarlos, así que solo se exponen los
  modos `OFF` y `AUTO`.
- No se procesan los horarios/programaciones (`schedule`), aunque la
  respuesta cruda de la API los incluye.
- La lectura de batería y versión OTA está implementada en `salus_api.py`
  pero no se expone como entidad todavía (ver `dev_reference/` en este repo).

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

1. **Ajustes → Dispositivos y servicios → Añadir integración** → busca
   "Salus iT500 Asíncrono".
2. Introduce:
   - **Nombre**: el que quieras para identificar el termostato.
   - **Usuario**: el email de tu cuenta en salus-it500.com.
   - **Contraseña**: la de esa cuenta.
   - **ID del dispositivo (devId)**: identificador numérico del termostato
     (visible en la URL del portal web al entrar en el control del
     dispositivo, `control.php?devId=XXXXXX`).

## Entidades creadas

| Entidad | Dominio | Descripción |
|---|---|---|
| `climate.salus_zona_1` / `climate.salus_zona_2` | `climate` | Control de cada zona |
| `number.salus_frost_temp` | `number` | Temperatura antihielo |
| `switch.salus_master_switch` | `switch` | Encendido/apagado global |

## Desarrollo

El código fuente vive en `custom_components/salus_it500/`. La carpeta
`dev_reference/` contiene plataformas descartadas (`sensor.py`,
`binary_sensor.py`) que se dejan como referencia para quien quiera
retomarlas, pero **no forman parte del paquete instalable**.

## Licencia

MIT — ver [LICENSE](LICENSE).
