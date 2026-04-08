"use client";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  return (
    <html lang="en">
      <body>
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            padding: "24px",
            background: "linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%)",
          }}
        >
          <section
            style={{
              width: "100%",
              maxWidth: "520px",
              padding: "32px",
              borderRadius: "20px",
              background: "#ffffff",
              boxShadow: "0 24px 60px rgba(15, 23, 42, 0.12)",
              textAlign: "center",
            }}
          >
            <p
              style={{
                margin: "0 0 12px",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                fontSize: "12px",
                color: "#64748b",
              }}
            >
              Application Error
            </p>
            <h1
              style={{
                margin: "0 0 12px",
                fontSize: "32px",
                color: "#0f172a",
              }}
            >
              Something went wrong
            </h1>
            <p
              style={{
                margin: "0 0 24px",
                color: "#475569",
                lineHeight: 1.6,
              }}
            >
              The page hit an unexpected error. You can try the action again or
              reload and continue where you left off.
            </p>
            <div
              style={{
                display: "flex",
                gap: "12px",
                justifyContent: "center",
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={() => reset()}
                style={{
                  border: "none",
                  borderRadius: "999px",
                  padding: "12px 20px",
                  background: "#0f172a",
                  color: "#ffffff",
                  cursor: "pointer",
                }}
              >
                Try Again
              </button>
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  borderRadius: "999px",
                  padding: "12px 20px",
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#0f172a",
                  cursor: "pointer",
                }}
              >
                Reload Page
              </button>
            </div>
            {error.message && (
              <p
                style={{
                  margin: "20px 0 0",
                  color: "#94a3b8",
                  fontSize: "14px",
                }}
              >
                {error.message}
              </p>
            )}
          </section>
        </main>
      </body>
    </html>
  );
}
