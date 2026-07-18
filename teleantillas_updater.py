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
import sys
from datetime import datetime

CONFIG_FILE = 'config.json'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Usa el token de GitHub Actions si existe
    token = os.getenv("GITHUB_TOKEN")
    if token:
        config["github_token"] = token

    return config

def get_dailymotion_stream(video_id, embedder):
    """Extrae stream de Dailymotion"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json',
        'Origin': 'https://www.dailymotion.com',
        'Referer': 'https://www.dailymotion.com/',
    })
    
    try:
        url = f"https://www.dailymotion.com/player/metadata/video/{video_id}"
        r = session.get(url, params={'embedder': embedder, 'referer': embedder}, timeout=15)
        data = r.json()
        
        if 'error' in data:
            return None
            
        qualities = data.get('qualities', {}).get('auto', [])
        if not qualities:
            return None
            
        master = qualities[0]['url']
        r = session.get(master, timeout=15)
        lines = r.text.split('\n')
        
        variants = []
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                res = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                if res and i+1 < len(lines):
                    url = lines[i+1].strip()
                    if url and not url.startswith('#'):
                        if not url.startswith('http'):
                            base = master.rsplit('/', 1)[0]
                            url = f"{base}/{url}"
                        variants.append({
                            'pixels': int(res.group(1)) * int(res.group(2)),
                            'url': url
                        })
        
        if variants:
            variants.sort(key=lambda x: x['pixels'], reverse=True)
            return variants[0]['url']
    except:
        pass
    return None

def obtener_stream(canal):
    """Obtiene stream según el tipo de canal"""
    if canal['tipo'] == 'dailymotion':
        return get_dailymotion_stream(canal['video_id'], canal['embedder'])
    elif canal['tipo'] == 'directo':
        # Para URLs que cambian por API propia
        try:
            r = requests.get(canal['url_extractor'], timeout=10)
            return r.json().get('url') or r.text.strip()
        except:
            return None
    return None

def get_github_file(config):
    """Descarga M3U actual"""
    url = f"https://api.github.com/repos/{config['github_user']}/{config['github_repo']}/contents/{config['file_path']}?ref={config['branch']}"
    headers = {'Authorization': f"token {config['github_token']}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {
                'content': base64.b64decode(data['content']).decode('utf-8'),
                'sha': data['sha']
            }
    except:
        pass
    return None

def find_and_replace(m3u_content, canal_nombre, new_url):
    """Busca y reemplaza URL del canal"""
    lines = m3u_content.split('\n')
    cambiado = False
    
    for i, line in enumerate(lines):
        if canal_nombre in line:
            for j in range(i+1, len(lines)):
                if lines[j].strip() and not lines[j].startswith('#'):
                    if lines[j].strip() != new_url:
                        lines[j] = new_url
                        cambiado = True
                        log(f"  {canal_nombre}: URL actualizada")
                    break
            break
    
    return '\n'.join(lines), cambiado

def update_github(config, content, sha, cambios):
    """Sube cambios a GitHub"""
    url = f"https://api.github.com/repos/{config['github_user']}/{config['github_repo']}/contents/{config['file_path']}"
    headers = {'Authorization': f"token {config['github_token']}"}
    
    msg = f"Auto-update: {len(cambios)} canal(es) actualizado(s)\n\n" + "\n".join(cambios)
    data = {
        'message': msg,
        'content': base64.b64encode(content.encode()).decode(),
        'sha': sha,
        'branch': config['branch']
    }
    
    try:
        r = requests.put(url, headers=headers, json=data, timeout=15)
        return r.status_code in [200, 201]
    except:
        return False

def main():
    print("=" * 60)
    print("MULTI-CANAL UPDATER")
    print("=" * 60)
    
    config = load_config()
    canales = config.get('canales', [])
    
    if not canales:
        log("No hay canales configurados")
        return 1
    
    # Descargar M3U actual
    log("Descargando NELSON.M3U...")
    file_data = get_github_file(config)
    if not file_data:
        log("✗ Error descargando de GitHub")
        return 1
    
    m3u_content = file_data['content']
    cambios_realizados = []
    
    # Procesar cada canal
    for canal in canales:
        log(f"Procesando: {canal['nombre']}")
        
        new_url = obtener_stream(canal)
        if not new_url:
            log(f"  ✗ No se pudo obtener stream")
            continue
        
        log(f"  ✓ Stream: {new_url[:50]}...")
        
        m3u_content, cambio = find_and_replace(m3u_content, canal['nombre'], new_url)
        
        if cambio:
            cambios_realizados.append(f"{canal['nombre'][:20]}...")
    
    # Subir si hubo cambios
    if cambios_realizados:
        log(f"Subiendo {len(cambios_realizados)} cambio(s) a GitHub...")
        if update_github(config, m3u_content, file_data['sha'], cambios_realizados):
            log("✓ GitHub actualizado")
        else:
            log("✗ Error subiendo a GitHub")
    else:
        log("✓ Sin cambios necesarios")
    
    log("Finalizado")
    return 0

if __name__ == "__main__":
    exit(main())