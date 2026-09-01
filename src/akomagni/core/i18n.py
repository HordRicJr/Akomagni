"""CLI message catalog (English / French)."""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = frozenset({"en", "fr"})

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "doctor.title": "Akomagni doctor — machine report",
        "doctor.os": "  OS          : {os} {release} ({machine})",
        "doctor.cpu": "  CPU         : {cores} cores / {threads} threads",
        "doctor.ram": "  RAM         : {available} GB free / {total} GB total",
        "doctor.disk": "  Disk free   : {free} GB",
        "doctor.gpu": "  GPU         : {name} ({vram} GB VRAM)",
        "doctor.gpu_none": "  GPU         : not detected (CPU inference)",
        "doctor.recommended_profile": "  Recommended profile : {profile}",
        "doctor.suggested_models": "  Suggested models    : {models}",
        "doctor.hint": "  You can install larger models if your machine allows.",
        "doctor.pull_hint": "  → akomagni model pull <name>",
        "memory.title": "Akomagni Memory",
        "memory.central": "  Central : {path}",
        "memory.project": "  Project : {path}",
        "memory.project_hint": "    (created on first project capture)",
        "memory.project_files": "    files         : {count} entries",
        "memory.saved_project": "Saved (project)",
        "memory.saved_central": "Saved (central)",
        "memory.promoted": "Promoted {count} file(s) to central memory.",
        "memory.no_pending": "No pending captures.",
        "memory.pending_title": "Pending captures ({scope})",
        "memory.approved": "Approved and saved",
        "memory.rejected": "Rejected",
        "memory.capture_preview": "Memory capture preview:",
        "memory.save_prompt": "Save to memory? [y/N/later]",
        "memory.saved_to": "Saved to memory",
        "memory.queued_capture": "Queued pending capture `{capture_id}` (akomagni memory approve {capture_id})",
        "inference.online": "Online",
        "inference.offline": "Offline",
        "inference.worker_stopped": "Inference worker stopped.",
        "inference.no_worker": "No background worker running.",
        "inference.no_worker_state": "No background worker state.",
        "config.initialized": "Config initialized",
        "config.language_current": "CLI language: {code}",
        "config.language_set": "CLI language set to {code}",
        "config.language_invalid": "Unsupported language: {code} (use en or fr)",
        "error": "Error",
        "flow.session_written": "Session written",
        "flow.skill_exec_failed": "Skill exec failed",
        "flow.workflow_rendered": "Workflow rendered",
        "skill.not_found": "Skill not found",
        "skill.none_found": "No skills found",
        "model.profile": "Profile",
        "model.models": "Models",
        "model.cache": "Cache",
        "model.ready": "Model ready",
        "run.cli_banner": "Akomagni CLI — type a message (Ctrl+C to quit).",
        "run.inference_online": "Inference online — {url}",
        "run.inference_offline": "Inference offline — routing only (run: akomagni serve)",
        "run.inference_failed": "Inference call failed — route/session kept.",
        "run.ide_unavailable": "Akomagni IDE is not available yet (planned v1.0).",
        "router.domain": "Domain",
    },
    "fr": {
        "doctor.title": "Akomagni doctor — rapport machine",
        "doctor.os": "  OS          : {os} {release} ({machine})",
        "doctor.cpu": "  CPU         : {cores} cœurs / {threads} threads",
        "doctor.ram": "  RAM         : {available} Go libres / {total} Go total",
        "doctor.disk": "  Disque libre: {free} Go",
        "doctor.gpu": "  GPU         : {name} ({vram} Go VRAM)",
        "doctor.gpu_none": "  GPU         : non détectée (inférence CPU)",
        "doctor.recommended_profile": "  Profil recommandé : {profile}",
        "doctor.suggested_models": "  Modèles suggérés  : {models}",
        "doctor.hint": "  Tu peux installer des modèles plus gros si ta machine le permet.",
        "doctor.pull_hint": "  → akomagni model pull <name>",
        "memory.title": "Akomagni Memory",
        "memory.central": "  Centrale : {path}",
        "memory.project": "  Projet   : {path}",
        "memory.project_hint": "    (créé à la première capture projet)",
        "memory.project_files": "    fichiers        : {count} entrées",
        "memory.saved_project": "Enregistré (projet)",
        "memory.saved_central": "Enregistré (central)",
        "memory.promoted": "{count} fichier(s) promu(s) vers la mémoire centrale.",
        "memory.no_pending": "Aucune capture en attente.",
        "memory.pending_title": "Captures en attente ({scope})",
        "memory.approved": "Approuvé et enregistré",
        "memory.rejected": "Rejeté",
        "memory.capture_preview": "Aperçu capture mémoire :",
        "memory.save_prompt": "Enregistrer en mémoire ? [y/N/plus tard]",
        "memory.saved_to": "Enregistré en mémoire",
        "memory.queued_capture": "Capture en attente `{capture_id}` (akomagni memory approve {capture_id})",
        "inference.online": "En ligne",
        "inference.offline": "Hors ligne",
        "inference.worker_stopped": "Worker d'inférence arrêté.",
        "inference.no_worker": "Aucun worker en arrière-plan.",
        "inference.no_worker_state": "Aucun état worker en arrière-plan.",
        "config.initialized": "Config initialisée",
        "config.language_current": "Langue CLI : {code}",
        "config.language_set": "Langue CLI définie sur {code}",
        "config.language_invalid": "Langue non supportée : {code} (utiliser en ou fr)",
        "error": "Erreur",
        "flow.session_written": "Session écrite",
        "flow.skill_exec_failed": "Échec exécution skill",
        "flow.workflow_rendered": "Workflow généré",
        "skill.not_found": "Skill introuvable",
        "skill.none_found": "Aucun skill trouvé",
        "model.profile": "Profil",
        "model.models": "Modèles",
        "model.cache": "Cache",
        "model.ready": "Modèle prêt",
        "run.cli_banner": "Akomagni CLI — saisissez un message (Ctrl+C pour quitter).",
        "run.inference_online": "Inférence en ligne — {url}",
        "run.inference_offline": "Inférence hors ligne — routage seul (lancer : akomagni serve)",
        "run.inference_failed": "Appel inférence échoué — route/session conservées.",
        "run.ide_unavailable": "Akomagni IDE n'est pas encore disponible (prévu v1.0).",
        "router.domain": "Domaine",
    },
}


def normalize_language(lang: str | None) -> str:
    """Return a supported language code, defaulting to English."""
    if not lang:
        return "en"
    code = lang.strip().lower().split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"


def resolve_language(config: dict[str, Any] | None = None) -> str:
    """Read CLI language from config (``language`` key)."""
    if config is None:
        from akomagni.core.config import load_config

        config = load_config()
    raw = config.get("language")
    if raw is None:
        prefs = config.get("memory", {}).get("central_dir")
        # Fallback: legacy preferences.yaml language when config has no key
        if prefs:
            pref_path = __import__("pathlib").Path(prefs) / "preferences.yaml"
            if pref_path.is_file():
                import yaml

                data = yaml.safe_load(pref_path.read_text(encoding="utf-8")) or {}
                raw = data.get("language")
    return normalize_language(str(raw) if raw else None)


def translate(key: str, lang: str, **kwargs: Any) -> str:
    """Look up *key* for *lang* and format with *kwargs*."""
    code = normalize_language(lang)
    catalog = _MESSAGES[code]
    template = catalog.get(key) or _MESSAGES["en"].get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template
