# AgriSense Frontend (Web)

This is the React-based frontend for the AgriSense platform.

## Setup

1.  **Install Dependencies:**
    ```bash
    npm install
    ```

2.  **Environment Variables:**
    The app uses `.env.development` by default. Ensure `VITE_API_BASE_URL` points to your backend (default: `http://localhost:8000`).

3.  **Start Development Server:**
    ```bash
    npm run dev
    ```

## Features Integrated

-   **Centralized API Client:** All calls use `src/api/client.ts`.
-   **Farm State Persistence:** `FarmSelector` stores the active `farm_id` in `localStorage`.
-   **Pest Detection:** React-native camera/upload component with Gemini vision analysis.
-   **Historical Trends:** Yield, Soil, and Pest history charts and timelines.
-   **System Health:** Live monitoring of backend services.

## Architecture

-   **`src/api/`**: Centralized API fetching and type definitions.
-   **`src/pages/`**: Main view components.
-   **`src/components/`**: Reusable UI primitives (badges, spinners, selectors).
-   **`src/hooks/`**: Custom React Query hooks (being migrated to direct client calls).
