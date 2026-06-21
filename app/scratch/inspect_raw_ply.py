import trimesh
import numpy as np

raw_ply = r"c:\Users\HP\pfe\app\static\uploads\boudha_20260506_234156\model_raw.ply"
tmesh = trimesh.load(raw_ply)
print("Type:", type(tmesh))
if isinstance(tmesh, trimesh.PointCloud):
    print("Vertices count:", len(tmesh.vertices))
    print("Bounds:", tmesh.bounds)
    print("Centroid:", tmesh.centroid)
    print("Sample vertices (first 10):")
    print(tmesh.vertices[:10])
else:
    print("Vertices:", len(tmesh.vertices))
    print("Faces:", len(tmesh.faces))
    print("Bounds:", tmesh.bounds)
