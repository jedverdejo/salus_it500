"""Comprobación contra TU termostato real. Solo lectura por defecto.

Variables de entorno: SALUS_USER, SALUS_PASS, SALUS_API_KEY
Uso (Windows):  py scripts\\live_check.py
Opciones:
  --refresh        envía F=1 (inocuo) y comprueba que el servidor lo acepta
  --set-mode ZONA MODO   (off|auto|manual) cambia de verdad el modo; pide confirmación
No imprime token, userId, devId, correo ni el atributo 'desc'.
"""
import argparse
import asyncio
import importlib.util
import os
import pathlib
import sys

import aiohttp

p = pathlib.Path(__file__).resolve().parent.parent / "custom_components/salus_it500/client.py"
spec = importlib.util.spec_from_file_location("client", p)
c = importlib.util.module_from_spec(spec)
sys.modules["client"] = c
spec.loader.exec_module(c)


async def main(args):
    for v in ("SALUS_USER", "SALUS_PASS", "SALUS_API_KEY"):
        if not os.environ.get(v):
            sys.exit(f"Falta la variable de entorno {v}")
    async with aiohttp.ClientSession() as s:
        cl = c.ArrayentClient(s, os.environ["SALUS_USER"], os.environ["SALUS_PASS"], os.environ["SALUS_API_KEY"])
        await cl.login()
        print("Login OK")
        devs = await cl.get_devices()
        print(f"Dispositivos: {len(devs)}")
        attrs = await cl.get_attributes()
        print(f"Atributos: {len(attrs)}  online={attrs.get('online')}")
        print(f"Antihielo S09 (valor bruto) = {attrs.get(c.ATTR_FROST)}")
        for z in (1, 2):
            if f"{c.zone_prefix(z)}84" in attrs:
                st = c.zone_state(attrs, z)
                print(f"Zona {z}: modo={st.mode.value} actual={st.current_temp} consigna={st.target_temp} calentando={st.heating}")
        if args.refresh:
            await cl.request_refresh()
            print("F=1 aceptado por el servidor")
        if args.set_temp:
            zone, temp = int(args.set_temp[0]), float(args.set_temp[1])
            pf = c.zone_prefix(zone)
            if c.decode_mode(attrs, zone) == c.Mode.OFF:
                sys.exit("La zona esta apagada; ponla en manual o auto primero")
            if input(f"Fijar consigna {temp} en zona {zone}? (si/no) ").strip().lower() != "si":
                return
            keys = [f"{pf}85", f"{pf}88", f"{pf}89", f"{pf}92", f"{pf}93", f"{pf}94"]
            print("antes:", {k: attrs.get(k) for k in keys})
            await cl.set_attribute(f"{pf}85", str(int(round(temp * 100))))
            print("A85 enviado")
            if zone == 2 or c.decode_mode(attrs, zone) == c.Mode.AUTO:
                await cl.set_attribute(f"{pf}88", "1")
                print("88=1 enviado")
            await cl.request_refresh()
            print("F=1 enviado")
            for i in range(1, 21):
                await asyncio.sleep(3)
                a = await cl.get_attributes()
                print(f"{i * 3:>3}s:", {k: a.get(k) for k in keys})
        if args.set_mode:
            zone, mode = int(args.set_mode[0]), c.Mode(args.set_mode[1])
            if input(f"Cambiar zona {zone} a {mode.value}? (si/no) ").strip().lower() != "si":
                return
            out = await cl.set_mode(zone, mode)
            print("Resultado:", c.decode_mode(out, zone).value)


ap = argparse.ArgumentParser()
ap.add_argument("--refresh", action="store_true")
ap.add_argument("--set-temp", nargs=2, metavar=("ZONA", "GRADOS"))
ap.add_argument("--set-mode", nargs=2, metavar=("ZONA", "MODO"))
asyncio.run(main(ap.parse_args()))
