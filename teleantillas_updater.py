#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Multi-Canal Updater - Actualiza varios canales automáticamente
"""

import requests
import re
import json
import base64
import os
from datetime import datetime


CONFIG_FILE = "config.json"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    token = os.getenv("GITHUB_TOKEN")

    if token:
        config["github_token"] = token

    print("CONFIG CARGADO:")

    for canal in config.get("canales", []):
        print("CANAL:", canal["nombre"])

    return config



def get_dailymotion_stream(video_id, embedder):
    """
    Extrae y valida stream de Dailymotion
    """

    session = requests.Session()

    session.headers.update({
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",

        "Accept":
        "application/json, text/plain, */*",

        "Accept-Language":
        "es-ES,es;q=0.9",

        "Origin":
        "https://www.dailymotion.com",

        "Referer":
        "https://www.dailymotion.com/"
    })


    try:

        log("  Obteniendo metadata Dailymotion...")


        metadata_url = (
            f"https://www.dailymotion.com/player/metadata/video/{video_id}"
        )


        params = {
            "embedder": embedder,
            "referer": embedder
        }


        r = session.get(
            metadata_url,
            params=params,
            timeout=15
        )


        data = r.json()


        if "error" in data:
            log("  ✗ Error en metadata")
            return None



        qualities = data.get("qualities", {})

        auto = qualities.get("auto", [])


        if not auto:
            log("  ✗ No existe calidad auto")
            return None



        master_url = auto[0]["url"]



        log("  Analizando calidades...")


        r = session.get(
            master_url,
            timeout=15
        )


        if r.status_code != 200:
            log(
                f"  ✗ Master playlist error {r.status_code}"
            )
            return None



        lines = r.text.splitlines()


        variants = []


        for i, line in enumerate(lines):

            if line.startswith("#EXT-X-STREAM-INF"):


                res = re.search(
                    r"RESOLUTION=(\d+)x(\d+)",
                    line
                )


                if res and i + 1 < len(lines):

                    url = lines[i + 1].strip()


                    if url and not url.startswith("#"):


                        if not url.startswith("http"):

                            base = master_url.rsplit("/",1)[0]

                            url = base + "/" + url



                        pixels = (
                            int(res.group(1)) *
                            int(res.group(2))
                        )


                        variants.append({
                            "pixels": pixels,
                            "url": url
                        })



        if not variants:
            log("  ✗ No hay variantes")
            return None



        variants.sort(
            key=lambda x:x["pixels"],
            reverse=True
        )



        # Probar enlaces

        for stream in variants:

            try:

                test = session.get(
                    stream["url"],
                    stream=True,
                    timeout=10
                )


                if test.status_code == 200:


                    chunk = next(
                        test.iter_content(1024),
                        None
                    )


                    if chunk:

                        log(
                            "  ✓ Stream válido encontrado"
                        )

                        return stream["url"]



            except Exception:

                continue



        log("  ✗ Ningún stream funciona")

        return None



    except Exception as e:

        log(f"  ✗ Error extractor: {e}")

        return None




def obtener_stream(canal):

    if canal["tipo"] == "dailymotion":

        return get_dailymotion_stream(
            canal["video_id"],
            canal["embedder"]
        )


    elif canal["tipo"] == "directo":

        try:

            r = requests.get(
                canal["url_extractor"],
                timeout=10
            )

            return (
                r.json().get("url")
                or
                r.text.strip()
            )

        except:

            return None


    return None




def get_github_file(config):

    url = (
        f"https://api.github.com/repos/"
        f"{config['github_user']}/"
        f"{config['github_repo']}/contents/"
        f"{config['file_path']}?"
        f"ref={config['branch']}"
    )


    headers = {
        "Authorization":
        f"token {config['github_token']}"
    }


    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )


        if r.status_code == 200:

            data = r.json()


            return {
                "content":
                base64.b64decode(
                    data["content"]
                ).decode("utf-8"),

                "sha":
                data["sha"]
            }


    except Exception:

        pass


    return None




def find_and_replace(m3u_content, canal_nombre, new_url):

    lines = m3u_content.split("\n")


    for i, line in enumerate(lines):

        if canal_nombre.lower() in line.lower():


            for j in range(
                i + 1,
                len(lines)
            ):


                actual = lines[j].strip()


                if (
                    actual == "#INSERTAR_LINK_AQUI"
                    or
                    (
                        actual
                        and
                        not actual.startswith("#")
                    )
                ):


                    if actual != new_url:

                        lines[j] = new_url

                        log(
                            f"  {canal_nombre}: URL actualizada"
                        )

                        return (
                            "\n".join(lines),
                            True
                        )


                    else:

                        log(
                            f"  {canal_nombre}: sin cambios"
                        )

                        return (
                            "\n".join(lines),
                            False
                        )


    log(
        f"  ✗ No encontrado: {canal_nombre}"
    )


    return (
        m3u_content,
        False
    )




def update_github(config, content, sha, cambios):


    url = (
        f"https://api.github.com/repos/"
        f"{config['github_user']}/"
        f"{config['github_repo']}/contents/"
        f"{config['file_path']}"
    )


    headers = {
        "Authorization":
        f"token {config['github_token']}"
    }


    data = {

        "message":
        f"Auto-update: {len(cambios)} canal(es)",

        "content":
        base64.b64encode(
            content.encode()
        ).decode(),

        "sha":
        sha,

        "branch":
        config["branch"]
    }



    try:

        r = requests.put(
            url,
            headers=headers,
            json=data,
            timeout=15
        )


        return r.status_code in [200,201]


    except:

        return False




def main():

    print("="*60)
    print("MULTI-CANAL UPDATER")
    print("="*60)


    config = load_config()


    canales = config.get(
        "canales",
        []
    )


    log(
        "Descargando NELSON.M3U..."
    )


    file_data = get_github_file(config)


    if not file_data:

        log(
            "✗ Error descargando M3U"
        )

        return 1



    contenido = file_data["content"]


    cambios = []



    for canal in canales:


        log(
            f"Procesando: {canal['nombre']}"
        )


        stream = obtener_stream(canal)


        if not stream:

            log(
                "  ✗ Stream inválido"
            )

            continue



        log(
            f"  ✓ Stream: {stream[:60]}..."
        )



        contenido, cambio = find_and_replace(
            contenido,
            canal["nombre"],
            stream
        )


        if cambio:

            cambios.append(
                canal["nombre"]
            )




    if cambios:


        log(
            f"Subiendo {len(cambios)} cambio(s) a GitHub..."
        )


        if update_github(
            config,
            contenido,
            file_data["sha"],
            cambios
        ):

            log(
                "✓ GitHub actualizado"
            )

        else:

            log(
                "✗ Error GitHub"
            )


    else:

        log(
            "✓ Sin cambios necesarios"
        )



    log(
        "Finalizado"
    )


    return 0




if __name__ == "__main__":

    exit(main())