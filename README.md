# Ernährungstagebuch

Ernährungstagebuch. Erstellt mit NiceGUI und CouchDB.

Datum: 20.06.2026
Author: Roland Kruggel
Lizenz: MIT

## Schnellstart

1. Virtuelle Umgebung anlegen und aktivieren
2. Abhaengigkeiten installieren
3. Anwendung starten

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Die Anwendung laeuft danach standardmaessig unter `http://localhost:9001`.

## Betrieb im LXC-Container (Debian/Ubuntu)

Fuer den normalen Webbetrieb brauchst du im Container nur Python und eine erreichbare CouchDB. Zusaetzliche Desktop-Pakete fuer Qt oder pywebview sind nicht noetig, solange die Anwendung im Browser laeuft.

### Systempakete installieren

```bash
apt update
apt install -y python3 python3-venv python3-pip git
useradd --system --create-home --home-dir /opt/ernaehrungstagebuch --shell /usr/sbin/nologin ernaehrungstagebuch
```

Wenn CouchDB im selben Container laufen soll, zusaetzlich:

```bash
apt install -y couchdb
systemctl enable --now couchdb
```

Alternativ kannst du eine externe CouchDB verwenden und nur die Verbindungsdaten in der Konfiguration setzen.

### Projekt installieren

```bash
git clone <REPO-URL> /opt/ernaehrungstagebuch
cd /opt/ernaehrungstagebuch
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp config.example.ini config.ini
chown -R ernaehrungstagebuch:ernaehrungstagebuch /opt/ernaehrungstagebuch
```

### config.ini anpassen

Beispiel:

```ini
[allgemein]
title=Ernaehrungstagebuch
host=0.0.0.0
port=9001
storage_secret=HIER_EIN_LANGES_ZUFAELLIGES_SECRET_SETZEN

[couchdb]
server_url=http://127.0.0.1:5984
database=ernaehrungstagebuch
username=admin
password=HIER_DAS_COUCHDB_PASSWORT_SETZEN
```

Wenn CouchDB auf einem anderen Host laeuft, musst du `server_url` entsprechend anpassen.

### Systemd-Service anlegen

Datei `/etc/systemd/system/ernaehrungstagebuch.service`:

```ini
[Unit]
Description=Ernaehrungstagebuch
After=network.target couchdb.service
Wants=couchdb.service

[Service]
Type=simple
User=ernaehrungstagebuch
Group=ernaehrungstagebuch
WorkingDirectory=/opt/ernaehrungstagebuch
ExecStart=/opt/ernaehrungstagebuch/.venv/bin/python /opt/ernaehrungstagebuch/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Service aktivieren und starten:

```bash
systemctl daemon-reload
systemctl enable --now ernaehrungstagebuch
systemctl status ernaehrungstagebuch
```

Wenn du keine lokale CouchDB im selben Container betreibst, kannst du `After=` und `Wants=` auf `network.target` reduzieren.

### Port freigeben

Die Anwendung lauscht standardmaessig auf Port `9001`.

Falls im Container `ufw` aktiv ist:

```bash
ufw allow 9001/tcp
```

Falls davor noch Proxmox-Firewall, Host-Firewall oder Router-Regeln aktiv sind, musst du Port `9001/tcp` dort ebenfalls freigeben.

### Logs und Tests

Service-Logs anzeigen:

```bash
journalctl -u ernaehrungstagebuch -f
```

Manueller Start zum Testen:

```bash
cd /opt/ernaehrungstagebuch
source .venv/bin/activate
python main.py
```
