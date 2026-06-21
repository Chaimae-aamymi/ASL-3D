import os
import re
import subprocess
import shutil
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

def get_exec_path(env_name, default):
    path = os.getenv(env_name, default)
    if path and os.path.exists(path):
        return path
    if path and env_name == 'COLMAP_PATH':
        bin_path = os.path.join(os.path.dirname(path), 'bin', 'colmap.exe')
        if os.path.exists(bin_path):
            return bin_path
    return path

COLMAP_EXE = get_exec_path('COLMAP_PATH', 'colmap')

print(f"[SFM-ENGINE] COLMAP path: {COLMAP_EXE}")

class SFMEngine:
    """Moteur de reconstruction via COLMAP et Optimisation via Blender pour ASL-3D"""
    
    def __init__(self, workspace_path, progress_callback=None, downscale_max_px=None):
        self.workspace = workspace_path
        self.images_path = workspace_path 
        self.database_path = os.path.join(workspace_path, "database.db")
        self.sparse_path = os.path.join(workspace_path, "sparse")
        self.dense_path = os.path.join(workspace_path, "dense")
        self.progress_callback = progress_callback
        # If set, images larger than this (max dimension) will be downscaled before COLMAP
        self.downscale_max_px = int(downscale_max_px) if downscale_max_px else None
        self._temp_images_dir = None
        self.log_dir = os.path.join(workspace_path, 'colmap_logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        os.makedirs(self.sparse_path, exist_ok=True)
        os.makedirs(self.dense_path, exist_ok=True)
        self._last_progress = None
        self.dense_reconstruction_ok = False
        self.textured_mesh_ply = None
        self.texture_atlas_png = None
        
    def _update_status(self, message, progress=None):
        if self.progress_callback:
            try:
                if progress is not None:
                    self.progress_callback(message, progress)
                else:
                    self.progress_callback(message)
            except Exception as e:
                print(f"[CALLBACK ERROR] {e}")

    def _run_logged_process(self, command, stage_name, timeout=14400, progress_min=None, progress_max=None):
        """Exécute un sous-processus COLMAP en journalisant sa sortie dans un fichier."""
        log_path = os.path.join(self.log_dir, f"{stage_name}.log")
        try:
            if os.path.exists(log_path):
                os.remove(log_path)
        except Exception:
            pass

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        with open(log_path, 'a', encoding='utf-8', errors='ignore') as log_file:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                line = line.rstrip('\r\n')
                formatted = f"[{stage_name}] {line}\n"
                sys.stdout.write(f"[COLMAP LOG:{stage_name}] {line}\n")
                sys.stdout.flush()
                try:
                    log_file.write(formatted)
                except Exception:
                    pass
                if progress_min is not None and progress_max is not None:
                    parsed = self._parse_progress_from_line(line, progress_min, progress_max)
                    if parsed is not None:
                        self._update_status(stage_name, parsed)

        process.wait(timeout=timeout)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)

    def _run_colmap_command(self, command, stage_name, timeout, retries=1, progress_min=None, progress_max=None):
        attempt = 1
        while attempt <= retries:
            try:
                self._update_status(f"{stage_name} (tentative {attempt}/{retries})...", progress_min)
                self._run_logged_process(command, stage_name, timeout=timeout, progress_min=progress_min, progress_max=progress_max)
                if progress_max is not None:
                    self._update_status(f"{stage_name} terminé.", progress_max)
                return
            except subprocess.TimeoutExpired:
                self._update_status(f"{stage_name} a expiré après {timeout}s", progress_min)
                if attempt == retries:
                    raise
            except subprocess.CalledProcessError as e:
                self._update_status(f"{stage_name} échoué (tentative {attempt}/{retries})", progress_min)
                if attempt == retries:
                    raise
            except Exception as e:
                self._update_status(f"Erreur pendant {stage_name}: {e}", progress_min)
                if attempt == retries:
                    raise
            attempt += 1
            backoff = 5 * attempt
            time.sleep(backoff)

    def run_colmap_pipeline(self):
        """Exécute le pipeline Structure-from-Motion complet"""
        try:
            # ── FIX: Toujours nettoyer le workspace COLMAP avant de commencer ──
            # Cela évite que le mapper échoue parce que la base de données d'une
            # ancienne tentative référence des chemins d'images qui n'existent plus
            # (ex: dossier images_downscaled supprimé à la fin d'un run précédent).
            try:
                if os.path.exists(self.database_path):
                    os.remove(self.database_path)
            except Exception as e:
                print(f"[SFM-ENGINE] Impossible de supprimer l'ancienne DB: {e}")
            try:
                if os.path.exists(self.sparse_path):
                    shutil.rmtree(self.sparse_path)
                if os.path.exists(self.dense_path):
                    shutil.rmtree(self.dense_path)
            except Exception as e:
                print(f"[SFM-ENGINE] Impossible de nettoyer sparse/dense: {e}")
            os.makedirs(self.sparse_path, exist_ok=True)
            os.makedirs(self.dense_path, exist_ok=True)

            # Prepare images (downscale if requested)
            images_dir = self._prepare_images_for_colmap()

            images = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg', '.jfif'))]
            if len(images) < 3:
                return False, "Au moins 3 images nécessaires."

            # Read COLMAP optimization env vars
            sift_max = int(os.getenv('COLMAP_SIFT_MAX_FEATURES', '4096'))
            num_threads = int(os.getenv('COLMAP_NUM_THREADS', '4'))
            use_gpu = os.getenv('COLMAP_USE_GPU', '0')
            matcher_env = os.getenv('COLMAP_MATCHER', 'auto').lower()
            matcher_threshold = int(os.getenv('COLMAP_AUTO_MATCHER_THRESHOLD', '200'))
            timeout = int(os.getenv('COLMAP_TIMEOUT', '3600'))
            retries = int(os.getenv('COLMAP_RETRIES', '2'))

            self._update_status("Extraction des points clés (SIFT)...", 10)
            feat_cmd = [
                COLMAP_EXE, "feature_extractor",
                "--database_path", self.database_path,
                "--image_path", images_dir,
                "--ImageReader.single_camera", "1"
            ]
            feat_cmd += [
                "--SiftExtraction.max_num_features", str(sift_max),
                "--FeatureExtraction.num_threads", str(num_threads),
                "--FeatureExtraction.use_gpu", use_gpu
            ]
            self._run_colmap_command(feat_cmd, 'feature_extractor', timeout, retries, progress_min=10, progress_max=25)

            self._update_status("Mise en correspondance des images (Matching)...", 25)
            # Choose matcher: exhaustive or vocab_tree (or auto)
            use_vocab = False
            if matcher_env == 'vocab_tree':
                use_vocab = True
            elif matcher_env == 'exhaustive':
                use_vocab = False
            else:
                # auto: choose vocab_tree for large image sets
                use_vocab = len(images) > matcher_threshold

            if use_vocab:
                matcher_cmd = [COLMAP_EXE, "vocab_tree_matcher", "--database_path", self.database_path]
                vocab_path = os.getenv('COLMAP_VOCAB_PATH')
                if vocab_path:
                    matcher_cmd += ["--VocabTreeMatching.vocab_tree_path", vocab_path]
            else:
                matcher_cmd = [COLMAP_EXE, "exhaustive_matcher", "--database_path", self.database_path]

            matcher_cmd += [
                "--FeatureMatching.num_threads", str(num_threads),
                "--FeatureMatching.use_gpu", use_gpu
            ]

            self._run_colmap_command(matcher_cmd, 'image_matching', timeout, retries, progress_min=25, progress_max=40)

            self._update_status("Reconstruction éparse (Mapper)...", 40)
            mapper_cmd = [
                COLMAP_EXE, "mapper",
                "--database_path", self.database_path,
                "--image_path", images_dir,
                "--output_path", self.sparse_path,
                "--Mapper.num_threads", str(num_threads)
            ]
            self._run_colmap_command(mapper_cmd, 'mapper', timeout, retries, progress_min=40, progress_max=50)

            # Vérification robuste du dossier du modèle généré
            model_dir = os.path.join(self.sparse_path, "0")
            if not os.path.exists(model_dir):
                if os.path.exists(os.path.join(self.sparse_path, "cameras.bin")):
                    model_dir = self.sparse_path
                else:
                    return False, "Échec de la reconstruction éparse (aucun modèle généré)."

            self._update_status("Distorsion des images (Undistortion)...", 50)
            self._run_colmap_command([
                COLMAP_EXE, "image_undistorter",
                "--image_path", images_dir,
                "--input_path", model_dir,
                "--output_path", self.dense_path,
                "--output_type", "COLMAP"
            ], 'image_undistorter', timeout, retries, progress_min=50, progress_max=60)

            has_cuda = True
            try:
                self._update_status("Stéréo dense (Patch Match)...", 60)
                self._run_colmap_command([
                    COLMAP_EXE, "patch_match_stereo",
                    "--workspace_path", self.dense_path,
                    "--PatchMatchStereo.geom_consistency", "0",
                    "--PatchMatchStereo.num_threads", str(num_threads)
                ], 'patch_match_stereo', timeout, retries, progress_min=60, progress_max=75)
            except Exception as e:
                print(f"[SFM-ENGINE] CUDA non disponible ({e}). Bascule sur pipeline CPU enrichi.")
                has_cuda = False

            self.dense_reconstruction_ok = has_cuda
            fused_ply = os.path.join(self.workspace, "fused.ply")
            meshed_ply = os.path.join(self.workspace, "model_raw.ply")

            if has_cuda:
                self._update_status("Fusion stéréo...", 75)
                self._run_colmap_command([
                    COLMAP_EXE, "stereo_fusion",
                    "--workspace_path", self.dense_path,
                    "--output_path", fused_ply
                ], 'stereo_fusion', timeout, retries, progress_min=75, progress_max=85)

                self._update_status("Génération du maillage (Poisson)...", 85)
                self._run_colmap_command([
                    COLMAP_EXE, "poisson_mesher",
                    "--input_path", fused_ply,
                    "--output_path", meshed_ply
                ], 'poisson_mesher', timeout, retries, progress_min=85, progress_max=88)

                if os.getenv('COLMAP_ENABLE_TEXTURE', '1') != '0':
                    self._run_mesh_texturer(meshed_ply, timeout, retries)
            else:
                # ── FALLBACK CPU ENRICHI (sans CUDA) ──────────────────────────
                # Étape 1 : exporter le nuage sparse depuis COLMAP
                self._update_status("CPU Fallback : Export du nuage de points sparse...", 65)
                self._run_colmap_command([
                    COLMAP_EXE, "model_converter",
                    "--input_path", model_dir,
                    "--output_path", fused_ply,
                    "--output_type", "PLY"
                ], 'model_converter', timeout, retries, progress_min=65, progress_max=72)

                # Étape 2 : enrichir le nuage sparse avec Open3D (upsampling CPU)
                self._update_status("CPU Fallback : Enrichissement du nuage de points (upsampling)...", 72)
                try:
                    import open3d as o3d
                    import numpy as np

                    pcd_sparse = o3d.io.read_point_cloud(fused_ply)
                    n_pts = len(pcd_sparse.points)
                    print(f"[CPU-FALLBACK] Nuage sparse : {n_pts} points")

                    if n_pts >= 3:
                        # Estimer les normales pour permettre l'upsampling
                        pcd_sparse.estimate_normals(
                            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.2, max_nn=30)
                        )
                        pcd_sparse.orient_normals_consistent_tangent_plane(k=min(30, n_pts - 1))

                        # Poisson surface reconstruction directement sur le sparse
                        # depth=8 pour CPU (moins lourd que depth=10)
                        mesh_tmp, densities_tmp = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                            pcd_sparse, depth=8
                        )
                        # Trimming agressif pour supprimer la bulle fantôme
                        dens_arr = np.asarray(densities_tmp)
                        threshold = np.percentile(dens_arr, 85)
                        mesh_tmp.remove_vertices_by_mask(dens_arr < threshold)

                        # Ré-échantillonner le maillage en nuage de points dense
                        pcd_enriched = mesh_tmp.sample_points_poisson_disk(
                            number_of_points=max(50000, n_pts * 20)
                        )
                        pcd_enriched.estimate_normals(
                            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30)
                        )
                        pcd_enriched.orient_normals_consistent_tangent_plane(k=30)

                        # Sauvegarder le nuage enrichi comme entrée pour le pipeline Open3D
                        o3d.io.write_point_cloud(fused_ply, pcd_enriched)
                        print(f"[CPU-FALLBACK] Nuage enrichi : {len(pcd_enriched.points)} points")
                    else:
                        print(f"[CPU-FALLBACK] Trop peu de points ({n_pts}), le nuage sera utilisé tel quel.")

                except Exception as enrich_err:
                    print(f"[CPU-FALLBACK] Enrichissement impossible : {enrich_err}. Utilisation du sparse brut.")

                self._update_status("CPU Fallback : Prêt pour le maillage final...", 80)
                try:
                    shutil.copy2(fused_ply, meshed_ply)
                except Exception as ce:
                    print(f"[SFM-ENGINE] Copie PLY échouée : {ce}")
            # Cleanup temporary downscaled images if created
            self._cleanup_temp_images()

            return True, meshed_ply
        except subprocess.TimeoutExpired:
            return False, "Erreur: Le traitement a dépassé la limite de temps."
        except Exception as e:
            # Ensure temp images are cleaned on error as well
            try:
                self._cleanup_temp_images()
            except Exception:
                pass
            return False, f"Erreur COLMAP : {str(e)}"

    def _prepare_images_for_colmap(self):
        """If downscale_max_px is set, create a temporary downscaled copy of images.
        Returns the path to the images directory to use for COLMAP.
        """
        if not self.downscale_max_px:
            return self.images_path

        src = self.images_path
        dest = os.path.join(self.workspace, 'images_downscaled')
        # If already prepared and exists, reuse it
        if self._temp_images_dir and os.path.exists(self._temp_images_dir):
            return self._temp_images_dir

        # Create/clear dest
        if os.path.exists(dest):
            try:
                shutil.rmtree(dest)
            except Exception:
                pass
        os.makedirs(dest, exist_ok=True)

        max_px = int(self.downscale_max_px)
        for f in os.listdir(src):
            if not f.lower().endswith(('.jpg', '.jpeg', '.png', '.jfif')):
                continue
            src_path = os.path.join(src, f)
            dst_path = os.path.join(dest, f)
            try:
                with Image.open(src_path) as im:
                    w, h = im.size
                    if max(w, h) > max_px:
                        scale = max_px / float(max(w, h))
                        new_size = (int(w * scale), int(h * scale))
                        im = im.resize(new_size, Image.LANCZOS)
                        im.save(dst_path, quality=90)
                    else:
                        shutil.copy2(src_path, dst_path)
            except Exception:
                # On any issue, fallback to copying raw file
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception:
                    pass

        self._temp_images_dir = dest
        return dest

    def _cleanup_temp_images(self):
        if self._temp_images_dir and os.path.exists(self._temp_images_dir):
            try:
                shutil.rmtree(self._temp_images_dir)
            except Exception:
                pass
            self._temp_images_dir = None

    def _run_mesh_texturer(self, meshed_ply, timeout, retries):
        """Projette les photos sur le maillage (atlas UV + texture.png)."""
        if not os.path.isfile(meshed_ply):
            print("[SFM-ENGINE] mesh_texturer ignoré : maillage introuvable.")
            return
        dense_images = os.path.join(self.dense_path, 'images')
        if not os.path.isdir(dense_images):
            print("[SFM-ENGINE] mesh_texturer ignoré : images dédistordies absentes.")
            return

        textured_dir = os.path.join(self.workspace, 'textured')
        if os.path.exists(textured_dir):
            try:
                shutil.rmtree(textured_dir)
            except Exception:
                pass
        os.makedirs(textured_dir, exist_ok=True)

        tex_scale = os.getenv('COLMAP_TEXTURE_SCALE', '1')
        num_threads = os.getenv('COLMAP_NUM_THREADS', '4')
        cmd = [
            COLMAP_EXE, "mesh_texturer",
            "--workspace_path", self.dense_path,
            "--input_path", meshed_ply,
            "--output_path", textured_dir,
            "--MeshTextureMapping.num_threads", str(num_threads),
            "--MeshTextureMapping.texture_scale_factor", str(tex_scale),
        ]
        try:
            self._update_status("Projection des couleurs photos (texturing)...", 88)
            self._run_colmap_command(
                cmd, 'mesh_texturer', timeout, retries,
                progress_min=88, progress_max=94,
            )
        except Exception as e:
            print(f"[SFM-ENGINE] mesh_texturer échoué : {e}")
            return

        mesh_path = os.path.join(textured_dir, 'mesh.ply')
        tex_path = os.path.join(textured_dir, 'texture.png')
        if os.path.isfile(mesh_path) and os.path.isfile(tex_path):
            self.textured_mesh_ply = mesh_path
            self.texture_atlas_png = tex_path
            print(f"[SFM-ENGINE] Texturing OK : {mesh_path}")
        else:
            print("[SFM-ENGINE] mesh_texturer terminé mais fichiers textured/ introuvables.")

    def _parse_progress_from_line(self, line, progress_min, progress_max):
        """Parse generic progress markers from COLMAP stdout lines."""
        line = line.strip()
        percent_match = re.search(r'(\d{1,3})\s*%', line)
        if percent_match:
            value = int(percent_match.group(1))
            if 0 <= value <= 100:
                scaled = progress_min + (progress_max - progress_min) * (value / 100.0)
                return min(progress_max, max(progress_min, int(scaled)))

        fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', line)
        if fraction_match:
            done = int(fraction_match.group(1))
            total = int(fraction_match.group(2))
            if total > 0:
                scaled = progress_min + (progress_max - progress_min) * (done / total)
                return min(progress_max, max(progress_min, int(scaled)))

        return None

    @staticmethod
    def _normalize_trimesh_for_display(tmesh):
        """Centre le maillage, retire les sommets aberrants et normalise l'échelle pour l'affichage."""
        import numpy as np
        import trimesh

        if isinstance(tmesh, trimesh.Scene):
            if not tmesh.geometry:
                return tmesh
            normalized = trimesh.Scene()
            for name, geom in tmesh.geometry.items():
                fixed = SFMEngine._normalize_trimesh_for_display(geom)
                if hasattr(fixed, 'vertices') and len(fixed.vertices) > 0:
                    normalized.add_geometry(fixed, node_name=name)
            return normalized if normalized.geometry else tmesh

        if isinstance(tmesh, trimesh.PointCloud):
            verts = np.asarray(tmesh.vertices)
            if len(verts) == 0:
                return tmesh
            colors = None
            try:
                colors = np.asarray(tmesh.colors)
            except Exception:
                pass
            if colors is None and hasattr(tmesh, 'visual'):
                try:
                    colors = np.asarray(tmesh.visual.vertex_colors)
                except Exception:
                    pass

            # Nettoyer les NaN/Inf
            nan_mask = np.isnan(verts).any(axis=1) | np.isinf(verts).any(axis=1)
            if nan_mask.any():
                print(f"[SFM-ENGINE] Found {nan_mask.sum()} NaN/Inf vertices in PointCloud. Cleaning...")
                verts = verts[~nan_mask]
                if colors is not None and len(colors) == len(nan_mask):
                    colors = colors[~nan_mask]
                if len(verts) == 0:
                    return tmesh

            center = verts.mean(axis=0)
            dists = np.linalg.norm(verts - center, axis=1)
            pct = float(os.getenv('MESH_OUTLIER_PERCENTILE', '98'))
            keep = dists <= float(np.percentile(dists, pct))
            verts = verts[keep] - center
            if colors is not None and len(colors) == len(keep):
                colors = colors[keep]
            ext = float(np.max(verts.max(axis=0) - verts.min(axis=0)))
            target = float(os.getenv('MESH_TARGET_SIZE', '2.0'))
            if ext > 1e-9:
                verts = verts * (target / ext)

            max_pts = int(os.getenv('MESH_MAX_POINT_CLOUD_PTS', '50000'))
            if len(verts) > max_pts:
                idx = np.linspace(0, len(verts) - 1, max_pts, dtype=int)
                verts = verts[idx]
                if colors is not None:
                    colors = colors[idx]

            if colors is not None and len(colors) == len(verts):
                return trimesh.PointCloud(vertices=verts, colors=colors)

            if len(verts) >= 4:
                try:
                    return trimesh.convex.convex_hull(verts)
                except Exception:
                    pass
            return trimesh.PointCloud(vertices=verts)

        if not isinstance(tmesh, trimesh.Trimesh):
            return tmesh

        verts = np.asarray(tmesh.vertices)
        if len(verts) == 0:
            return tmesh

        # Nettoyer les NaN/Inf
        nan_mask = np.isnan(verts).any(axis=1) | np.isinf(verts).any(axis=1)
        if nan_mask.any():
            print(f"[SFM-ENGINE] Found {nan_mask.sum()} NaN/Inf vertices in Trimesh. Cleaning...")
            tmesh.update_vertices(~nan_mask)
            verts = np.asarray(tmesh.vertices)
            if len(verts) == 0:
                return tmesh

        # Remove outlier vertices
        center = verts.mean(axis=0)
        dists = np.linalg.norm(verts - center, axis=1)
        pct = float(os.getenv('MESH_OUTLIER_PERCENTILE', '98'))
        thresh = float(np.percentile(dists, pct))
        tmesh.update_vertices(dists <= thresh)
        if len(tmesh.vertices) == 0:
            return tmesh

        # Keep only the largest connected component
        try:
            components = trimesh.graph.connected_components(
                tmesh.face_adjacency, min_len=3
            )
            if components and len(components) > 1:
                largest = max(components, key=lambda c: len(c))
                mask = np.zeros(len(tmesh.faces), dtype=bool)
                mask[largest] = True
                tmesh.update_faces(mask)
                tmesh.remove_unreferenced_vertices()
        except Exception:
            pass

        # Laplacian smoothing for surface homogeneity
        try:
            smooth_iter = int(os.getenv('MESH_SMOOTH_ITERATIONS', '3'))
            if smooth_iter > 0 and len(tmesh.faces) > 0:
                tmesh = trimesh.smoothing.filter_laplacian(
                    tmesh, iterations=smooth_iter, lamb=0.5, volume_constraint=False
                )
        except Exception:
            pass

        if len(tmesh.vertices) == 0:
            return tmesh

        tmesh.vertices -= tmesh.centroid
        ext = float(np.max(tmesh.extents))
        target = float(os.getenv('MESH_TARGET_SIZE', '2.0'))
        if ext > 1e-9:
            tmesh.apply_scale(target / ext)
        return tmesh

    @staticmethod
    def _attach_texture_visual(mesh, texture_path):
        """Associe texture.png au maillage si le PLY n'a pas de matériau."""
        import trimesh
        from PIL import Image

        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
            return mesh
        if getattr(mesh.visual, 'kind', None) == 'texture':
            return mesh

        img = Image.open(texture_path)
        try:
            uv = mesh.visual.uv
        except Exception:
            uv = None
        if uv is None or len(uv) != len(mesh.vertices):
            uv = mesh.vertices[:, :2].copy()
            uv -= uv.min(axis=0)
            span = uv.max(axis=0)
            span[span < 1e-9] = 1.0
            uv /= span

        material = trimesh.visual.texture.SimpleMaterial(image=img)
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=img, material=material)
        return mesh

    @staticmethod
    def _prepare_textured_scene_for_export(scene):
        """Centrage + échelle uniforme (préserve les UV)."""
        import trimesh

        if isinstance(scene, trimesh.Trimesh):
            scene = trimesh.Scene(geometry={'mesh': scene})

        if not scene.geometry:
            return scene

        scene.rezero()
        extents = scene.extents
        if extents is None:
            return scene
        max_ext = float(max(extents))
        target = float(os.getenv('MESH_TARGET_SIZE', '2.0'))
        if max_ext > 1e-9:
            scene.apply_scale(target / max_ext)
        return scene

    def export_textured_glb(self, output_glb):
        """Exporte mesh.ply + texture.png en GLB pour le viewer web."""
        import trimesh

        mesh_path = self.textured_mesh_ply
        tex_path = self.texture_atlas_png
        if not mesh_path or not os.path.isfile(mesh_path):
            return False
        if not tex_path or not os.path.isfile(tex_path):
            return False

        self._update_status("Export GLB texturé pour le navigateur...", 95)
        try:
            loaded = trimesh.load(mesh_path, process=False)
            if isinstance(loaded, trimesh.Trimesh):
                loaded = self._attach_texture_visual(loaded, tex_path)
                scene = trimesh.Scene(geometry={'textured_mesh': loaded})
            elif isinstance(loaded, trimesh.Scene):
                scene = loaded
                for name, geom in scene.geometry.items():
                    if isinstance(geom, trimesh.Trimesh):
                        scene.geometry[name] = self._attach_texture_visual(geom, tex_path)
            else:
                return False

            scene = self._prepare_textured_scene_for_export(scene)
            scene.export(output_glb)

            tex_dest = output_glb.replace('.glb', '_texture.png')
            try:
                shutil.copy2(tex_path, tex_dest)
            except Exception:
                pass

            self._update_status("Modèle 3D texturé exporté.", 100)
            return True
        except Exception as e:
            print(f"[SFM-ENGINE] export_textured_glb échoué : {e}")
            return False

    def export_final_glb(self, output_glb, fallback_ply):
        """Préfère le GLB texturé ; sinon maillage simplifié Open3D."""
        if self.textured_mesh_ply and self.texture_atlas_png:
            if self.export_textured_glb(output_glb):
                return True
            print("[SFM-ENGINE] Fallback vers export Open3D sans texture.")
        return self.optimize_with_open3d(fallback_ply, output_glb)

    def optimize_with_open3d(self, input_ply, output_glb):
        """Pipeline CPU complet : débruitage → densité uniforme → Poisson → lissage → export GLB homogène"""
        self._update_status("Optimisation Open3D : pipeline maillage homogène...", 90)
        try:
            import trimesh
            import numpy as np

            has_o3d = False
            try:
                import open3d as o3d
                has_o3d = True
            except ImportError:
                print("[OPEN3D] Open3D absent — fallback Trimesh direct.")

            # ── FALLBACK SANS OPEN3D (Si la bibliothèque n'est pas installée) ──
            if not has_o3d:
                tmesh = trimesh.load(input_ply)
                tmesh = self._normalize_trimesh_for_display(tmesh)
                if isinstance(tmesh, trimesh.PointCloud):
                    self._update_status("Nettoyage des points aberrants...", 92)
                    try:
                        points = np.asarray(tmesh.vertices)
                        colors = None
                        if hasattr(tmesh, 'colors') and tmesh.colors is not None:
                            colors = np.asarray(tmesh.colors)
                        elif hasattr(tmesh, 'visual') and hasattr(tmesh.visual, 'vertex_colors'):
                            colors = np.asarray(tmesh.visual.vertex_colors)

                        from scipy.spatial import KDTree, Delaunay
                        k = int(os.getenv('MESH_OUTLIER_NEIGHBORS', '20'))
                        std_ratio = float(os.getenv('MESH_OUTLIER_STD_RATIO', '1.0'))
                        tree = KDTree(points)
                        dists, _ = tree.query(points, k=k+1)
                        mean_dists = dists[:, 1:].mean(axis=1)
                        global_mean = mean_dists.mean() if len(mean_dists) > 0 else 0.05
                        global_std = mean_dists.std() if len(mean_dists) > 0 else 0.01
                        threshold = global_mean + std_ratio * global_std
                        
                        keep_mask = mean_dists < threshold
                        points = points[keep_mask]
                        if colors is not None and len(colors) == len(keep_mask):
                            colors = colors[keep_mask]

                        self._update_status("Reconstruction surface (Delaunay 2.5D)...", 94)
                        pts_centered = points - points.mean(axis=0)
                        cov = np.cov(pts_centered.T)
                        _, eigenvectors = np.linalg.eigh(cov)
                        proj_axes = eigenvectors[:, 1:]
                        pts_2d = pts_centered @ proj_axes
                        tri_2d = Delaunay(pts_2d)
                        faces_2d = tri_2d.simplices
                        
                        mesh_reconstructed = trimesh.Trimesh(vertices=points, faces=faces_2d, vertex_colors=colors)
                        edges = mesh_reconstructed.edges_unique
                        edge_lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
                        
                        max_edge_len = global_mean * 4.0
                        bad_edges_mask = edge_lengths > max_edge_len
                        bad_edges_set = set(np.where(bad_edges_mask)[0])
                        
                        keep_faces = []
                        for i, f_edge_indices in enumerate(mesh_reconstructed.faces_unique_edges):
                            if not any(e in bad_edges_set for e in f_edge_indices):
                                keep_faces.append(i)
                                
                        mesh_reconstructed = trimesh.Trimesh(vertices=points, faces=faces_2d[keep_faces], vertex_colors=colors)
                        mesh_reconstructed.remove_unreferenced_vertices()
                            
                        self._update_status("Lissage Laplacien du maillage...", 96)
                        try:
                            import trimesh.smoothing
                            smooth_iter = int(os.getenv('MESH_SMOOTH_ITERATIONS', '5'))
                            if smooth_iter > 0:
                                trimesh.smoothing.filter_laplacian(mesh_reconstructed, iterations=smooth_iter, volume_constraint=False)
                        except Exception as se:
                            print(f"[RECONSTRUCTION FALLBACK] Lissage échoué : {se}")
                            
                        tmesh = mesh_reconstructed
                        self._update_status("Export maillage homogène sans Open3D.", 100)
                    except Exception as fe:
                        print(f"[RECONSTRUCTION FALLBACK ERROR] {fe}")
                        self._update_status("Export nuage de points direct (erreur reconstruction).", 100)
                else:
                    self._update_status("Export maillage direct via Trimesh.", 100)
                
                tmesh.export(output_glb)
                return True

            # ── PIPELINE PRINCIPAL OPEN3D (CPU / Sans CUDA) ───────────────────
            # C'est ici que s'appliquent tes 12 espaces réglementaires d'indentation !
            pcd = o3d.io.read_point_cloud(input_ply)
            if pcd.is_empty():
                mesh_raw = o3d.io.read_triangle_mesh(input_ply)
                pcd.points = mesh_raw.vertices
                pcd.colors = mesh_raw.vertex_colors

            # Étape 1 : Filtre statistique
            self._update_status("Open3D : Filtrage des points aberrants (Stat)...", 91)
            nb_neighbors = int(os.getenv('MESH_OUTLIER_NEIGHBORS', '25'))
            std_ratio = float(os.getenv('MESH_OUTLIER_STD_RATIO', '1.0'))
            pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)
            
            # Étape 2 : Filtre par rayon (Radius Outlier - détruit les éclats isolés)
            radius_pts = int(os.getenv('MESH_RADIUS_OUTLIER_PTS', '15'))
            radius_r = float(os.getenv('MESH_RADIUS_OUTLIER_R', '0.07'))
            pcd, _ = pcd.remove_radius_outlier(nb_points=radius_pts, radius=radius_r)

            # Étape 3 : Voxel Downsampling (Stabilise la géométrie de Poisson)
            voxel_size = float(os.getenv('MESH_VOXEL_SIZE', '0.015'))
            if voxel_size > 0:
                pcd = pcd.voxel_downsample(voxel_size=voxel_size)

            # Étape 4 : Estimation des normales
            self._update_status("Open3D : Estimation des normales...", 93)
            nn_max = int(os.getenv('MESH_NORMAL_MAX_NN', '30'))
            n_radius = float(os.getenv('MESH_NORMAL_RADIUS', '0.12'))
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=n_radius, max_nn=nn_max))
            
            # Orientation cohérente des normales (Crucial anti-hérisson)
            tangent_k = int(os.getenv('MESH_NORMAL_TANGENT_PLANE_K', '120'))
            pcd.orient_normals_consistent_tangent_plane(k=tangent_k)

            # Étape 5 : Reconstruction de Poisson
            self._update_status("Open3D : Reconstruction de Poisson (CPU)...", 95)
            poisson_depth = int(os.getenv('MESH_POISSON_DEPTH', '9'))
            mesh_out, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=poisson_depth
            )

            # 🌟 Étape 6 : LE FILTRE DE DENSITÉ ANTI-HÉRISSON 🌟
            self._update_status("Open3D : Suppression des mailles fantômes...", 97)
            
            # Application agressive du trimming (85%)
            densities = np.asarray(densities)
            density_threshold = np.percentile(densities, 85)
            mesh_out.remove_vertices_by_mask(densities < density_threshold)
            
            # Suppression des vertices et faces isolées sous le seuil
            vertices_to_remove = densities < density_threshold
            mesh_out.remove_vertices_by_mask(vertices_to_remove)

            # Étape 7 : Lissage final Taubin
            smooth_iter = int(os.getenv('MESH_SMOOTH_ITERATIONS', '5'))
            if smooth_iter > 0:
                self._update_status("Open3D : Lissage géométrique...", 98)
                mesh_out = mesh_out.filter_smooth_taubin(number_of_iterations=smooth_iter)

            # Étape 8 : Décimation pour alléger le fichier GLB final
            decimate_ratio = float(os.getenv('MESH_DECIMATE_RATIO', '0.6'))
            if decimate_ratio < 1.0 and len(mesh_out.triangles) > 0:
                target_triangles = int(len(mesh_out.triangles) * decimate_ratio)
                mesh_out = mesh_out.simplify_quadric_error(target_number_of_triangles=target_triangles)

            mesh_out.compute_vertex_normals()

            # ── Exportation GLB ───────────────────────────────────────────────
            self._update_status("Open3D : Exportation vers le format GLB...", 99)
            o3d.io.write_triangle_mesh(output_glb, mesh_out)
            
            self._update_status("Pipeline CPU Open3D terminé sans artéfacts !", 100)
            return True

        except Exception as e:
            print(f"[SFM-ENGINE] Erreur critique Open3D : {e}")
            self._update_status(f"Échec optimisation Open3D: {str(e)}", 100)
            return False
        
# ── POINT D'ENTRÉE GLOBAL POUR APP.PY ──
def run_advanced_reconstruction(input_dir, output_dir, progress_callback=None, downscale_max_px=None):
    """
    Fonction globale appelée par app.py pour instancier la classe SFMEngine
    et lancer le traitement complet avec suivi de la progression.
    """
    # Initialisation du moteur avec les bons arguments
    engine = SFMEngine(
        workspace_path=input_dir,
        progress_callback=progress_callback,
        downscale_max_px=downscale_max_px
    )
    
    # 1. Pipeline COLMAP (Reconstruction brute)
    success, result = engine.run_colmap_pipeline()
    if not success:
        return False
    
    # 2. Export GLB
    raw_ply = result
    success_opt = engine.export_final_glb(output_dir, raw_ply)
    
    return bool(success_opt)