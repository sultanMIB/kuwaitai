# 🚀 How to Run the App

### 🧩 1. Create a Conda Environment
```bash
conda create -n rag python=3.10
```
▶️ 2. Activate the Environment
```bash
conda init
conda activate rag
```
🛠️ 3. Install Dependencies
```bash
pip install -U pip setuptools wheel
```
Then install PyTorch (CPU version by default):
```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.3.1
```
Now install the rest of the requirements:
```bash
pip install -r requirements.txt --no-cache-dir
```
💡 If GPU installation fails (common on Windows), just re-run the CPU command above — it will work fine for embeddings.

🧱 4. Database Configuration

If you plan to create your own database, make sure to update the following files:

alembic.ini

.env.postgres

These should contain the correct PostgreSQL connection details before running migrations.

⚙️ 5. Environment Variables
Before running the app, set the following environment variables (for example, in .env):

EMBEDDING_BACKEND=HUGGINGFACE
EMBEDDING_MODEL_ID=intfloat/multilingual-e5-large
EMBEDDING_MODEL_SIZE=1024
GENERATION_BACKEND=COHERE
GENERATION_MODEL_ID=command-r
COHERE_API_KEY=your_key_here

🧠 The model intfloat/multilingual-e5-large supports Arabic + English + many languages and works great for multilingual embeddings.

▶️ 7. Run the App

You can start the FastAPI app locally using:

```bash
uvicorn scr.main:app --reload
```
