# Publishing Notebooks to GitHub Pages

## Quick Setup

Your project is now configured to automatically publish notebooks to GitHub Pages!

### Files Created

1. **`docs/index.html`** - Landing page for your GitHub Pages site
2. **`.nojekyll`** - Tells GitHub not to use Jekyll processing
3. **`.github/workflows/deploy-notebooks.yml`** - GitHub Actions workflow for automatic deployment

### How to Enable GitHub Pages

1. **Push your changes to GitHub:**
   ```powershell
   git add .
   git commit -m "Add GitHub Pages setup"
   git push
   ```

2. **Enable GitHub Pages in your repository:**
   - Go to your repository on GitHub
   - Click **Settings** → **Pages**
   - Under "Build and deployment":
     - Source: Select **GitHub Actions**
   - Save the changes

3. **Wait for deployment:**
   - The workflow will automatically run on push
   - Go to the **Actions** tab to monitor progress
   - Once complete, your site will be live at: `https://YOUR_USERNAME.github.io/northeastern_visualization/`

### Manual Conversion (local only)

To convert notebooks to HTML locally without pushing:

```powershell
# Convert single notebook
python -m nbconvert --to html notebooks/01_schema_overview.ipynb --output-dir=docs

# Convert all notebooks
python -m nbconvert --to html notebooks/*.ipynb --output-dir=docs

python3 -m nbconvert --to html --execute --ExecutePreprocessor.timeout=120 notebooks/*.ipynb --output-dir=docs 2>&1
```

### Adding More Notebooks

1. Create your notebook in the `notebooks/` folder
2. Add a link to `docs/index.html` (or the workflow will auto-convert it)
3. Push to GitHub - the workflow automatically converts and deploys

### Note on Plotly Visualizations

The standard HTML export may not render interactive Plotly charts perfectly. If you need better Plotly support, consider:
- Using `nbconvert --to html --template lab` 
- Or switching to **Jupyter Book** for a more robust publishing solution

### Alternative: Using Jupyter Book

For a more professional documentation site with better interactive chart support:

```powershell
pip install jupyter-book
jupyter-book create mybook
# Move notebooks to mybook/ and configure _config.yml
jupyter-book build mybook
```

Then update the GitHub Actions workflow to build and deploy the Jupyter Book.
