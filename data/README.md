# Place the dataset here before training.

Recommended layout:

```
data/
  dataset/
    real/
      real_001.jpg
      real_002.jpg
      ...
    fake/
      fake_001.jpg
      fake_002.jpg
      ...
```

Notes:

- Use clear, well-lit photos of Indian currency notes.
- Include different denominations, lighting conditions, angles, and both sides
  of the note where possible.
- Keep the classes balanced (similar number of real and fake images).
- Aim for at least a few hundred images per class for meaningful results.
- Folder names become the class labels. Exactly two folders are required.
- This folder is intentionally excluded from git because datasets are large.
