## Plan: Relancer reconstruction propre et combler les manquants

TL;DR - Vérifier et compléter les étapes manquantes pour obtenir `fused.ply` puis le GLB final : garantir que les commandes COLMAP de fusion et maillage s'exécutent, ajouter logs persistants, augmenter timeouts/retries, s'assurer des dépendances (Open3D/trimesh), et conserver un flux sûr de nettoyage/re-run.

**Steps**
1. Vérifier dépendances installées (*non bloquant*): `open3d`, `trimesh`, `numpy`, `scipy` dans `app/requirements.txt` et en runtime. Si manquant, ajouter et installer. (*parallel with step 2*)
2. Ajouter logging persistant COLMAP: capturer stdout/stderr de chaque appel COLMAP dans `static/uploads/<dataset>/colmap_logs/<stage>.log`. Retourner codes d'erreur pour prise de décision. (*depends on step 1*)
3. S'assurer que `stereo_fusion` et `poisson_mesher` sont invoqués correctement dans `app/sfm_engine.py` et que leurs chemins de sortie (`fused.ply`, `model_raw.ply`) sont attendus. Si fusion échoue, ré-exécuter uniquement la fusion (après vérifier l'existence des depth maps). (*depends on step 2*)
4. Augmenter timeouts et ajouter retries pour les sous-processus COLMAP (ex: timeout 3600s, 2 retries avec backoff). Loguer chaque tentative. (*depends on step 2*)
5. Vérifier cohérence DB/images: quand `images_downscaled` est créé, supprimer `database.db`, `sparse/`, `dense/` — déjà fait. Ajouter une validation qui compare les résolutions comptées et arrête si mismatch détecté. (*parallel with step 2*)
6. Ajouter un petit wrapper de relance pour la fusion: si `fused.ply` absent à la fin, capturer logs et réessayer la fusion jusqu'à N fois puis alerter l'utilisateur. (*depends on step 3 et 4*)
7. Sauvegarder artefacts et logs: conserver `colmap_logs/`, `images_downscaled/`, `fused.ply`, `model_raw.ply`, `final.glb` sous `static/uploads/<dataset>/` et créer une archive `reconstruction_<timestamp>.zip` à la fin. (*parallel with step 3*)
8. Vérification manuelle automatique: après run, exécuter checks (existence de `fused.ply`, taille > 0, existence GLB). Si échec, fournir le dernier log pertinent et l'étape à relancer. (*depends on steps 2-7*)

**Relevant files**
- `app/sfm_engine.py` — ajouter logging, retries, timeout, fusion rerun wrapper, validation des images/DB.
- `app/run_and_monitor.py` — afficher et stocker périodiquement l'état, inclure références aux logs et aux artefacts.
- `app/app.py` — s'assurer que les callbacks `progress_cb` reçoivent les messages d'erreur et les stockent en base.
- `app/requirements.txt` — vérifier/ajouter `open3d`, `trimesh` si absent.

**Verification**
1. Lancer nettoyage manuel: supprimer `database.db`, `sparse/`, `dense/` et `images_downscaled/` (fait).
2. Lancer reconstruction monitorée; vérifier qu'un fichier `colmap_logs/stereo_fusion.log` est produit.
3. Vérifier l'existence et taille de `fused.ply` et `model_raw.ply` après fusion.
4. Vérifier que `final.glb` est généré et non vide.
5. En cas d'échec, récupérer et relancer l'étape échouée avec les logs capturés.

**Decisions / Assumptions**
- Rester CPU-only (COLMAP bat sans CUDA).
- Conserver remplacement de Blender par Open3D (déjà fait).
- Priorité: pipeline end-to-end pour le dataset `boudha_20260506_234156`.

**Further Considerations**
1. Docker: construire l'image complète reste problématique à cause de `tensorflow` dans `requirements.txt`. Option: séparer composants lourds ou utiliser un base-image préconstruit.
2. Si COLMAP version locale ne supporte pas certaines options, garder appels minimalistes et robustes.

---

**Confirmations utilisateur**
- Dataset: boudha_20260506_234156
- Nettoyage avant run: Non — conserver les fichiers existants
- Timeout COLMAP: 3600 secondes
- Retries fusion: 2

Next: Appliquer les patches demandés et lancer un run de test sur le dataset `boudha_20260506_234156` sans supprimer les artefacts existants, en respectant les timeouts/retries ci‑dessous.
