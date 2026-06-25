# installation auf einem proxmoc lxc Container

## Proxmox 

------------------------------------------------------------------------------------

proxmox lxc installieren

```bash
cpu   1
Ram   512 M
HD    8 G
```
 
## Server configurieren

------------------------------------------------------------------------------------

### Auf dem Server (login: root)

Nach installation des lxc:

```bash
apt update
apt upgrade
apt install -y python3 python3-venv python3-pip git
```

User installieren und Benutzer in die sudo-Gruppe aufnehmen

```bash
adduser roland
usermod -aG sudo roland
```

Das Verzeichnis für die Software anlegen

```bash
mkdir -p /opt/ernaehrungstagebuch
chown -R roland:roland /opt/ernaehrungstagebuch
```

## Uhr geht auf dem Server 2 Std nach

------------------------------------------------------------------------------------

Prüfen

Auf dem Proxmox-Host und im Container jeweils:

```bash
date
timedatectl status
```

Wenn der Host schon 2 Stunden falsch ist, musst du den Host korrigieren. Der Container folgt dann automatisch.

Host korrigieren

Auf dem Proxmox-Host:

```bash
timedatectl set-timezone Europe/Berlin
timedatectl set-ntp true
timedatectl status
```

Achte darauf, dass dort bei Time zone Europe/Berlin steht und System clock synchronized: yes.

Container korrigieren

Wenn nur der Container falsch wirkt, setze dort ebenfalls die Zeitzone:

```bash
apt install -y tzdata
timedatectl set-timezone Europe/Berlin
timedatectl status
```

Danach
Deinen Dienst neu starten:

```bash
systemctl restart ernaehrungstagebuch
```



## Install auf server

------------------------------------------------------------------------------------

### Auf dem Client (Der Entwicklungsrechner) (login: roland)

Das Kopierprogramm liegt in der Entwicklung. Es kopiert die gesamte entwicklung auf den Server.

```bash
rsynccopy
```




## SSH-Key

------------------------------------------------------------------------------------

### Auf dem Client (login: roland)

```bash
ls -la ~/.ssh
```

Wenn dort schon z. B. id_ed25519 und id_ed25519.pub liegen, kannst du den vorhandenen Key benutzen.

Falls noch kein Key existiert, einen neuen erzeugen

```bash
ssh-keygen -t ed25519 -C "ernaehrungstagebuch-deploy"
```

Einfach mit Enter bestätigen, dann landet der Key standardmäßig in:

```bash
~/.ssh/id_ed25519
~/.ssh/id_ed25519.pub
```

Den öffentlichen Key auf den Zielserver kopieren

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub roland@192.168.178.224
```

Dabei wirst du ein letztes Mal nach dem Passwort gefragt. Danach liegt dein Public Key auf dem Server in 

```bash
~/.ssh/authorized_keys.
```

### Auf dem Server

Wenn ein Fehler auftritt weil man schon zu viel probiert hat

```bash
ssh-keygen -f '/home/roland/.ssh/known_hosts' -R '192.168.178.224'
```



## Starten als Dienst  (login: root)

------------------------------------------------------------------------------------

Auf dem Server diese Datei anlegen:

```bash
/etc/systemd/system/ernaehrungstagebuch.service
```

das ist der inhalt

```bash
[Unit]
Description=Ernaehrungstagebuch
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=roland
Group=roland
WorkingDirectory=/opt/ernaehrungstagebuch
ExecStart=/opt/ernaehrungstagebuch/.venv/bin/python /opt/ernaehrungstagebuch/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Danach den Dienst aktivieren und starten:

```bash
systemctl daemon-reload
systemctl enable ernaehrungstagebuch
systemctl start ernaehrungstagebuch
```

Prüfen

```bash
systemctl status ernaehrungstagebuch
systemctl is-enabled ernaehrungstagebuch
journalctl -u ernaehrungstagebuch -f
```

## Entwicklung 

.venv erstellen

```bash
cd /opt/ernaehrungstagebuch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Jetzt kann an das Programm aufrufwen

```bash
python main.py
```



## restart dienst nach update von programm

```bash
systemctl restart ernaehrungstagebuch
```

### Dienst geändert wurde

Wenn du den systemd-Dienst selbst geändert hast, brauchst du vor dem Neustart noch:

```bash
systemctl daemon-reload
systemctl restart ernaehrungstagebuch
```
