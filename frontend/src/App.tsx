function App() {
  const backendUrl =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

  return (
    <div className="app">
      <main className="hero">
        <h1>LongNovelInsight</h1>
        <p className="subtitle">Local-first long novel analysis lab</p>
        <div className="card">
          <p>
            Backend API: <code>{backendUrl}</code>
          </p>
          <p className="hint">
            Start the backend with{" "}
            <code>python -m uvicorn main:app --reload --port 8000</code>
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
