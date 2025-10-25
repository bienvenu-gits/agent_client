# 🖥️ Watchman Agent Client

**Agent d'inventaire système moderne et multi-plateforme** développé en Python. Alternative à l'agent GLPI avec interface web intégrée et architecture modulaire.

## 🎯 Vue d'ensemble

**Watchman Agent Client** est un système complet de collecte d'informations système qui :
- Collecte automatiquement les données matérielles et logicielles de vos machines
- Transmet les inventaires à un serveur central via API REST sécurisée
- Fournit une interface web locale pour le contrôle manuel
- Fonctionne comme service système sur Windows, Linux et macOS

### ✨ Fonctionnalités principales

- 📊 **Collecte complète** : Matériel, logiciels, réseau, processus système
- 🔄 **Planification flexible** : Quotidien, hebdomadaire, mensuel ou à la demande
- 🌐 **Interface web intégrée** : Contrôle et monitoring via navigateur
- ⚡ **Envoi immédiat** : Déclenchement manuel d'inventaire
- 🛠️ **Multi-plateforme** : Windows, Linux, macOS
- 🔧 **Déploiement simplifié** : Installation automatique en tant que service

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│           SERVEUR CENTRAL           │
│        (API REST + Base de          │
│         données inventaire)         │
└─────────────────┬───────────────────┘
                  │ HTTPS/JSON + Auth
                  ▼
┌─────────────────────────────────────┐
│      WATCHMAN AGENT CLIENT          │
│  ┌─────────────┐ ┌─────────────────┐ │
│  │ Collecteurs │ │ Interface Web   │ │
│  │ Spécialisés │ │  localhost:8080 │ │
│  │(System,HW,  │ │   Dashboard +   │ │
│  │SW,Network)  │ │   Contrôles     │ │
│  └─────────────┘ └─────────────────┘ │
│  ┌─────────────┐ ┌─────────────────┐ │
│  │ Planificateur│ │ Service/Daemon  │ │
│  │  (schedule) │ │  Multi-Platform │ │
│  └─────────────┘ └─────────────────┘ │
└─────────────────────────────────────┘
```

## 🚀 Installation Rapide

### Windows
```powershell
# Télécharger l'installeur MSI
.\watchman-agent-client-setup.msi

# Ou via PowerShell
powershell -ExecutionPolicy Bypass -File install.ps1
```

### Linux (Ubuntu/Debian)
```bash
# Via package DEB
sudo dpkg -i watchman-agent-client.deb

# Ou via script
curl -sSL https://get.watchman-agent-client.com | sudo bash
```

### macOS
```bash
# Via package PKG
sudo installer -pkg watchman-agent-client.pkg -target /

# Ou via script
curl -sSL https://get.watchman-agent-client.com | sudo bash
```

## 🌐 Interface Web Locale

L'agent expose une interface web complète accessible localement :

**URL** : `http://localhost:8080`

### Fonctionnalités de l'interface
- **📊 Tableau de bord** : Vue d'ensemble du statut système et de l'agent
- **🔄 Collecte manuelle** : Déclenchement immédiat d'inventaire
- **📤 Envoi forcé** : Transmission directe vers le serveur
- **🧪 Test de connectivité** : Vérification de la liaison serveur
- **⚙️ Configuration** : Modification des paramètres en temps réel
- **📝 Logs en direct** : Visualisation des journaux d'activité
- **ℹ️ Informations système** : Détails des données collectées

### Pages disponibles
- `/` - Dashboard principal avec contrôles
- `/logs` - Consultation des logs avec filtrage
- `/config` - Interface de configuration
- `/about` - Informations sur l'agent et le système

## 📋 Données Collectées

L'agent collecte de façon structurée et sécurisée les informations suivantes :

### 🖥️ Informations Système
- **Identification** : Nom d'hôte, domaine, utilisateur, UUID machine
- **OS** : Version, architecture, build, langue
- **Performance** : CPU, mémoire, charge système, uptime
- **Stockage** : Disques, partitions, espace libre/utilisé

### 🔧 Matériel (Hardware)
- **Processeur** : Modèle, fréquence, cœurs, architecture
- **Mémoire** : RAM totale, modules installés, vitesse
- **Stockage** : Disques durs, SSD, contrôleurs
- **Réseau** : Cartes réseau, interfaces, vitesses
- **Périphériques** : USB, PCI, moniteurs

### 💾 Logiciels (Software)
- **Applications installées** : Nom, version, éditeur, date d'installation
- **Services système** : Services en cours, démarrés, arrêtés
- **Pilotes** : Pilotes installés et leurs versions
- **Mises à jour** : Patches système installés

### 🌐 Configuration Réseau
- **Interfaces** : Ethernet, WiFi, VPN, Loopback
- **Adressage** : IP, masques, passerelles, DNS
- **Connectivité** : Ports ouverts, connexions actives
- **Configuration** : DHCP, statique, proxy

### 📊 Exemple de structure JSON
```json
{
  "assets": [{
    "collection_timestamp": "2024-01-15T14:30:00Z",
    "agent_version": "1.0.0",
    "hostname": "PC-BUREAU-01",
    "architecture": "x86_64",
    "os": "Windows 11 Pro 22H2",
    "ip": "192.168.1.100",
    "mac": "aa:bb:cc:dd:ee:ff",
    "cpu": {
      "model": "Intel Core i7-12700K",
      "cores": 12,
      "frequency": "3600 MHz"
    },
    "memory": {
      "total": "32 GB",
      "available": "18 GB"
    },
    "applications": [
      {
        "name": "Microsoft Office 365",
        "version": "16.0.15128.20224",
        "publisher": "Microsoft Corporation"
      }
    ],
    "network_interfaces": [
      {
        "name": "Ethernet",
        "ip": "192.168.1.100",
        "mac": "aa:bb:cc:dd:ee:ff",
        "speed": "1000 Mbps"
      }
    ]
  }]
}
```

## ⚙️ Configuration

### 📁 Emplacements des fichiers
```bash
# Linux/macOS
/etc/watchman-agent-client/config.ini
/var/log/watchman-agent-client/agent.log

# Windows
C:\Program Files\WatchmanAgentClient\config\config.ini
C:\Program Files\WatchmanAgentClient\logs\agent.log
```

### 📝 Structure du fichier de configuration
```ini
[server]
# URL du serveur de collecte d'inventaire
url = https://inventaire.entreprise.com/api/v1/inventory
# Token d'authentification
auth_token = your-secret-auth-token-here
# Timeout des requêtes (secondes)
timeout = 30
# Vérification SSL (recommandé : true)
verify_ssl = true

[agent]
# Fréquence de reporting automatique
reporting_frequency = daily  # hourly, daily, weekly, monthly
# Niveau de log
log_level = INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
# Modules de collecte activés
collect_software = true
collect_hardware = true
collect_network = true
collect_services = true

[web_interface]
# Activer l'interface web
enabled = true
# Port d'écoute
port = 8080
# Interface d'écoute (127.0.0.1 = local uniquement)
host = 127.0.0.1

[logging]
# Fichier de log (auto-détecté si vide)
log_file =
# Taille maximale des logs (bytes)
max_log_size = 10485760  # 10MB
# Nombre de fichiers de sauvegarde
backup_count = 5
```

### 🌐 Configuration via Interface Web
1. **Accéder** : `http://localhost:8080/config`
2. **Modifier** : Paramètres serveur, agent, logging
3. **Tester** : Bouton de test de connectivité
4. **Sauvegarder** : Application immédiate des changements

## 🔧 Utilisation

### 🎮 Modes de fonctionnement

#### 1. Mode Service (Recommandé)
```bash
# L'agent fonctionne en arrière-plan comme service système
# Collecte automatique selon la planification configurée
# Interface web disponible en permanence sur http://localhost:8080
```

#### 2. Mode Interface Web
```bash
# Accès au contrôle manuel via navigateur
http://localhost:8080
```

#### 3. Mode Ligne de Commande
```bash
# Windows
C:\Program Files\WatchmanAgentClient\WatchmanAgentClient.exe [options]

# Linux/macOS
watchman-agent-client [options]

# Options disponibles :
--mode collect          # Collecte uniquement
--mode send            # Envoi uniquement
--mode collect-send    # Collecte + envoi
--mode web            # Interface web uniquement
--mode test           # Test de connectivité
--config-file PATH    # Fichier de config personnalisé
--log-level LEVEL     # Niveau de log temporaire
--output-file PATH    # Sauvegarde JSON locale
```

### 🚀 Scénarios d'utilisation courants

#### Envoi immédiat d'inventaire
```bash
# Via interface web (le plus simple)
http://localhost:8080 → "Collecter et Envoyer"

# Via ligne de commande
watchman-agent-client --mode collect-send
```

#### Test de configuration
```bash
# Test de connectivité serveur
watchman-agent-client --mode test

# Test avec logs détaillés
watchman-agent-client --mode test --log-level DEBUG
```

#### Collecte locale sans envoi
```bash
# Génération d'un fichier JSON local
watchman-agent-client --mode collect --output-file inventaire.json
```

### Gestion du Service
```bash
# Linux (systemd)
sudo systemctl status watchman-agent-client
sudo systemctl restart watchman-agent-client

# Windows (Services)
sc query "WatchmanAgentClient"
sc stop "WatchmanAgentClient"
sc start "WatchmanAgentClient"

# macOS (launchd)
sudo launchctl list | grep inventory
sudo launchctl unload /Library/LaunchDaemons/com.watchman.agent.client.plist
```

## 🛡️ Sécurité et Fiabilité

### 🔒 Mesures de sécurité
- **Interface locale uniquement** : Web UI accessible que depuis 127.0.0.1
- **Authentification serveur** : Token API sécurisé pour les communications
- **Chiffrement SSL/TLS** : Toutes les communications serveur chiffrées
- **Privilèges minimaux** : Service avec droits système restreints
- **Validation des données** : Sanitisation de toutes les entrées
- **Logs sécurisés** : Aucun secret ou token dans les fichiers de log

### ⚡ Fiabilité
- **Gestion d'erreurs robuste** : Récupération automatique des pannes temporaires
- **Retry automatique** : Nouvelle tentative en cas d'échec réseau
- **Monitoring intégré** : Surveillance de l'état de l'agent
- **Logs rotatifs** : Gestion automatique de l'espace disque
- **Mode dégradé** : Fonctionnement partiel en cas de problème

### 🔄 Performance
- **Collecte optimisée** : Cache intelligent pour éviter les re-collectes
- **Multithreading** : Collecte parallèle pour de meilleures performances
- **Mémoire maîtrisée** : Gestion optimale des ressources système
- **Planification intelligente** : Évitement des pics de charge système

## 📈 Comparaison avec les alternatives

| Fonctionnalité | GLPI Agent | OCS Agent | **Watchman Agent** |
|---|---|---|---|
| Interface web locale | ❌ | ❌ | ✅ |
| Dashboard en temps réel | ❌ | ❌ | ✅ |
| API REST moderne | ❌ | ❌ | ✅ |
| Configuration web | ❌ | ❌ | ✅ |
| Architecture modulaire | ⚠️ | ⚠️ | ✅ |
| Multi-plateforme | ✅ | ✅ | ✅ |
| Open Source | ✅ | ✅ | ✅ |
| Déploiement simple | ❌ | ❌ | ✅ |
| Logs consultables | ⚠️ | ⚠️ | ✅ |
| Test connectivité | ❌ | ❌ | ✅ |

## 🚧 Développement et Architecture

### 🔧 Prérequis développeur
- **Python 3.8+** (testé jusqu'à 3.13)
- **Packages système** : psutil, requests, flask, schedule
- **Outils build** : PyInstaller, cx_Freeze (< Python 3.13)
- **OS** : Windows 10+, Linux, macOS 10.14+

### 🏗️ Installation environnement de développement
```bash
# Cloner le projet
git clone https://github.com/votre-repo/watchman-agent-client
cd watchman-agent-client

# Installer les dépendances
pip install -r requirements.txt

# Lancement en mode développement
python -m agent.main --mode web --log-level DEBUG

# Tests
python -m pytest tests/
```

### 📁 Architecture détaillée du code
```
watchman-agent-client/
├── agent/                          # 🏠 Code principal
│   ├── main.py                    #    Point d'entrée avec argparse
│   ├── core/                      # 🧠 Logique métier
│   │   ├── __init__.py
│   │   ├── collector.py           #    Orchestrateur principal
│   │   ├── sender.py              #    Envoi serveur + auth
│   │   ├── scheduler.py           #    Planification automatique
│   │   ├── config.py              #    Gestion configuration
│   │   └── logger.py              #    Logging centralisé
│   ├── collectors/                # 📊 Collecteurs spécialisés
│   │   ├── __init__.py
│   │   ├── base.py                #    Classe abstraite
│   │   ├── system.py              #    Infos système (psutil)
│   │   ├── hardware.py            #    Matériel détaillé
│   │   ├── software.py            #    Applications installées
│   │   ├── network.py             #    Configuration réseau
│   │   └── platform/              # 🖥️ Spécifique par OS
│   │       ├── windows.py         #    Collecteur Windows (WMI)
│   │       ├── linux.py           #    Collecteur Linux (/proc)
│   │       └── macos.py           #    Collecteur macOS
│   ├── web/                       # 🌐 Interface web Flask
│   │   ├── __init__.py
│   │   ├── app.py                 #    Application Flask
│   │   ├── templates/             # 📄 Templates HTML
│   │   │   ├── base.html          #    Template de base
│   │   │   ├── index.html         #    Dashboard principal
│   │   │   ├── logs.html          #    Consultation logs
│   │   │   ├── config.html        #    Configuration
│   │   │   └── about.html         #    Informations système
│   │   └── static/                # 🎨 Assets statiques
│   │       ├── css/style.css      #    Styles CSS
│   │       └── js/main.js         #    JavaScript
│   └── services/                  # 🔧 Services système
│       ├── __init__.py
│       ├── base_service.py        #    Interface service abstraite
│       ├── windows_service.py     #    Service Windows
│       ├── linux_daemon.py       #    Daemon systemd Linux
│       └── macos_launchd.py       #    Service launchd macOS
├── config/                        # ⚙️ Configuration
│   └── default.conf               #    Configuration par défaut
├── setup/                         # 📦 Scripts d'installation
│   ├── windows/                   # 🪟 Windows
│   │   ├── install.bat            #    Installation Windows
│   │   ├── uninstall.bat          #    Désinstallation
│   │   └── service.py             #    Utilitaires service
│   ├── linux/                     # 🐧 Linux
│   │   ├── install.sh             #    Installation Linux
│   │   ├── uninstall.sh           #    Désinstallation
│   │   └── watchman.service       #    Fichier systemd
│   └── macos/                     # 🍎 macOS
│       ├── install.sh             #    Installation macOS
│       └── com.watchman.plist     #    Fichier launchd
├── build/                         # 🏗️ Scripts de build
│   ├── build_packages.py          #    Build universel
│   ├── build_windows.py           #    Build Windows spécifique
│   ├── build_simple.py            #    Build PyInstaller simple
│   └── build_portable.py          #    Version portable
├── tests/                         # 🧪 Tests
│   ├── test_collectors.py         #    Tests collecteurs
│   ├── test_web_interface.py      #    Tests interface web
│   └── test_services.py           #    Tests services
├── requirements.txt               # 📋 Dépendances
├── setup.py                       # 📦 Setup cx_Freeze
├── watchman.spec                  # 📦 Spec PyInstaller
└── README.md                      # 📖 Documentation
```

### 🔌 Points d'extension

#### Ajouter un nouveau collecteur
```python
# agent/collectors/mon_collecteur.py
from .base import BaseCollector

class MonCollector(BaseCollector):
    def collect(self):
        # Votre logique de collecte
        return {"ma_donnee": "valeur"}
```

#### Ajouter une route web
```python
# agent/web/app.py
@app.route('/ma-route')
def ma_route():
    return render_template('ma_page.html')
```

### 🧪 Build et tests
```bash
# Build pour la plateforme courante
python build_packages.py

# Build toutes plateformes (CI/CD)
python build_packages.py --platform all

# Tests unitaires
python -m pytest tests/ -v

# Tests d'intégration
python -m pytest tests/integration/ -v

# Linter et formatage
python -m flake8 agent/
python -m black agent/
```

## 🔧 Débogage et Résolution de Problèmes

### 🐛 Problèmes courants

#### L'agent ne démarre pas
```bash
# Vérifier les logs
# Windows
type "C:\Program Files\WatchmanAgentClient\logs\agent.log"

# Linux/macOS
tail -f /var/log/watchman-agent-client/agent.log

# Vérifier la configuration
watchman-agent-client --mode test --log-level DEBUG
```

#### Interface web inaccessible
```bash
# Vérifier que le service est démarré
# Windows
sc query "WatchmanAgentClient"

# Linux
systemctl status watchman-agent-client

# Vérifier le port
netstat -an | grep 8080
```

#### Échec d'envoi au serveur
```bash
# Test de connectivité
watchman-agent-client --mode test

# Vérifier la configuration réseau
ping votre-serveur.com
nslookup votre-serveur.com

# Test SSL
openssl s_client -connect votre-serveur.com:443
```

### 📊 Logs et Monitoring

#### Niveaux de log disponibles
- **DEBUG** : Toutes les informations de débogage
- **INFO** : Informations générales d'activité
- **WARNING** : Alertes non critiques
- **ERROR** : Erreurs récupérables
- **CRITICAL** : Erreurs fatales

#### Emplacements des logs
```bash
# Windows
C:\Program Files\WatchmanAgentClient\logs\
├── agent.log                    # Log principal
├── collector.log               # Logs de collecte
├── sender.log                  # Logs d'envoi
└── web.log                     # Logs interface web

# Linux/macOS
/var/log/watchman-agent-client/
├── agent.log                    # Log principal
├── collector.log               # Logs de collecte
├── sender.log                  # Logs d'envoi
└── web.log                     # Logs interface web
```

## 📚 Documentation et Support

### 📖 Ressources
- **Documentation complète** : Wiki du projet avec guides détaillés
- **API Reference** : Documentation des APIs REST et modules Python
- **Guides de déploiement** : Instructions spécifiques par environnement
- **FAQ** : Questions fréquentes et solutions

### 🤝 Communauté et Support
- **GitHub Issues** : Signalement de bugs et demandes de fonctionnalités
- **GitHub Discussions** : Questions techniques et partage d'expérience
- **Wiki** : Documentation collaborative et guides utilisateurs
- **Releases** : Historique des versions et notes de mise à jour

### 🔄 Cycle de développement
- **Releases mineures** : Corrections de bugs (ex: 1.0.1)
- **Releases majeures** : Nouvelles fonctionnalités (ex: 1.1.0)
- **Support LTS** : Support étendu pour versions de production
- **Préversions** : Bêta et RC pour tests anticipés

## 🚀 Feuille de Route

### Version 1.1 (À venir)
- 🔐 **Authentification avancée** : Support LDAP/AD
- 📊 **Métriques étendues** : Monitoring performance temps réel
- 🌍 **Interface multilingue** : Support français/anglais
- 📦 **Packages Snap/Flatpak** : Distribution Linux simplifiée

### Version 1.2 (Futur)
- 🤖 **API GraphQL** : API moderne pour intégrations
- 📱 **Application mobile** : Monitoring depuis mobile
- 🔄 **Synchronisation bidirectionnelle** : Configuration centralisée
- 🧪 **Tests automatisés** : CI/CD complet

## 📄 Licence et Contributions

### 📋 Licence
**MIT License** - Utilisation libre pour projets commerciaux et open source.

### 🤝 Comment contribuer
```bash
# 1. Fork du projet
git clone https://github.com/votre-username/watchman-agent-client
cd watchman-agent-client

# 2. Créer une branche
git checkout -b feature/ma-fonctionnalite

# 3. Développer et tester
python -m pytest tests/
python -m flake8 agent/

# 4. Commit et Push
git commit -m "feat: ajout de ma fonctionnalité"
git push origin feature/ma-fonctionnalite

# 5. Créer une Pull Request
```

### 🏆 Contributeurs
Merci à tous les contributeurs qui rendent ce projet possible !

---

**⭐ N'oubliez pas de mettre une étoile au projet si vous le trouvez utile !**

**🤝 Contributions, suggestions et retours d'expérience sont les bienvenus !**