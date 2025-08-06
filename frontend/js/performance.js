import { onCLS, onFID, onLCP } from "https://unpkg.com/web-vitals@5.1.0/dist/web-vitals.js";

const { AWS_CONFIG } = window;

// Function to send performance data to the backend
async function sendMetric(metric) {
  // TODO: Get the API Gateway URL from a shared config
  const apiGatewayUrl = AWS_CONFIG.apiGatewayUrl;
  if (!apiGatewayUrl) {
    console.warn("Performance Monitor: API Gateway URL not configured. Metric not sent.");
    return;
  }

  // We need to be authenticated to send metrics
  const idToken = localStorage.getItem("oauth_id_token");
  if (!idToken) {
    console.log("Performance Monitor: User not authenticated. Metric not sent.");
    return;
  }

  try {
    console.log(`📈 Performance Monitor: Sending metric ${metric.name}`, metric);
    await fetch(`${apiGatewayUrl}/performance/frontend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // TODO: Get the token from the AuthManager
        Authorization: `Bearer ${idToken}`
      },
      body: JSON.stringify(metric),
      // Use keepalive so the request can outlive the page
      keepalive: true
    });
  } catch (error) {
    console.error("Performance Monitor: Error sending metric:", error);
  }
}

// Handler for Core Web Vitals
function logMetric(metric) {
  sendMetric({
    name: metric.name,
    value: metric.value,
    delta: metric.delta,
    id: metric.id,
    timestamp: new Date().toISOString()
  });
}

// Handler for unhandled JavaScript errors
function logError(errorEvent) {
  sendMetric({
    name: "JavaScriptError",
    value: {
      message: errorEvent.message,
      filename: errorEvent.filename,
      lineno: errorEvent.lineno,
      colno: errorEvent.colno
    },
    timestamp: new Date().toISOString()
  });
}

// Initializes the performance monitoring system
export function initPerformanceMonitor() {
  try {
    console.log("🚀 Performance Monitor: Initializing...");

    // Set up listeners for Core Web Vitals
    onCLS(logMetric);
    onFID(logMetric);
    onLCP(logMetric);

    // Set up a global error handler for unhandled exceptions
    const originalOnError = window.onerror;
    window.onerror = (message, source, lineno, colno, error) => {
      logError({ message, filename: source, lineno, colno, error });

      // If there was a previous error handler, call it
      if (originalOnError) {
        return originalOnError(message, source, lineno, colno, error);
      }

      // Otherwise, return false to let the browser's default handler run
      return false;
    };

    console.log("✅ Performance Monitor: Initialized successfully.");
  } catch (error) {
    console.error("❌ Performance Monitor: Failed to initialize:", error);
  }
}
