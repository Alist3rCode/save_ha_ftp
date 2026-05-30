# HA FTP Backup

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Intégration Home Assistant (HACS) qui effectue des sauvegardes complètes de HAOS et les envoie automatiquement vers un serveur FTP configurable.

## Fonctionnalités

- Sauvegarde complète de l'installation HAOS via l'API Supervisor
- Envoi automatique vers un serveur FTP (plain FTP ou FTPS/TLS)
- Fréquence de sauvegarde configurable (de 1 heure à 1 an)
- Rétention automatique : suppression des anciennes sauvegardes selon le nombre maximum défini
- Service `ha_ftp_backup.run_backup` pour déclencher une sauvegarde immédiate
- Capteur d'état (`sensor`) avec attributs détaillés (date dernière sauvegarde, taille, prochaine sauvegarde, erreur éventuelle)

## Prérequis

- Home Assistant OS (HAOS) avec le Supervisor
- Accès à un serveur FTP

## Installation via HACS

1. Dans HACS, allez dans **Intégrations** → **⋮** → **Dépôts personnalisés**
2. Ajoutez l'URL `https://github.com/alist3rcode/save_ha_ftp` avec la catégorie **Intégration**
3. Recherchez **HA FTP Backup** et installez-la
4. Redémarrez Home Assistant
5. Dans **Paramètres → Appareils et services → Ajouter une intégration**, cherchez **HA FTP Backup**

## Configuration

| Paramètre | Obligatoire | Défaut | Description |
|---|---|---|---|
| Hôte FTP | Oui | — | Adresse IP ou hostname du serveur FTP |
| Port FTP | Non | 21 | Port du serveur FTP |
| Utilisateur | Oui | — | Identifiant FTP |
| Mot de passe | Oui | — | Mot de passe FTP |
| Dossier distant | Non | `/ha_backups` | Chemin sur le serveur FTP |
| FTPS (TLS) | Non | Non | Activer le chiffrement TLS |
| Fréquence (heures) | Non | 24 | Intervalle entre chaque sauvegarde |
| Nombre max de sauvegardes | Non | 7 | Les plus anciennes sont supprimées automatiquement |

## Service

```yaml
service: ha_ftp_backup.run_backup
```

Déclenche immédiatement une sauvegarde complète sans attendre la prochaine échéance planifiée.

## Capteur

L'entité `sensor.ftp_backup_status` expose :

| État | Signification |
|---|---|
| `idle` | Aucune sauvegarde effectuée depuis le démarrage |
| `running` | Sauvegarde en cours |
| `ok` | Dernière sauvegarde réussie |
| `error` | La dernière sauvegarde a échoué |

### Attributs

| Attribut | Description |
|---|---|
| `last_backup` | Horodatage ISO 8601 de la dernière sauvegarde réussie |
| `last_backup_size_mb` | Taille en Mo |
| `next_backup` | Horodatage prévu de la prochaine sauvegarde |
| `total_backups_on_ftp` | Nombre de sauvegardes présentes sur le FTP |
| `last_error` | Message d'erreur de la dernière tentative échouée |

## Exemple d'automatisation

```yaml
automation:
  - alias: "Notifier si sauvegarde FTP échouée"
    trigger:
      - platform: state
        entity_id: sensor.ftp_backup_status
        to: "error"
    action:
      - service: notify.mobile_app
        data:
          title: "Sauvegarde FTP échouée"
          message: "{{ state_attr('sensor.ftp_backup_status', 'last_error') }}"
```
