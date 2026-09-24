import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Background from "./components/Background";
import AuthPage from "./pages/AuthPage";
import DebuggerPage from "./pages/DebuggerPage";
import HistoryPage from "./pages/HistoryPage";
import PracticePage from "./pages/PracticePage";
import PracticeProblemPage from "./pages/PracticeProblemPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Background />
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          {/* everything below needs a signed-in user */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DebuggerPage />} />
            <Route path="/practice" element={<PracticePage />} />
            <Route path="/practice/:id" element={<PracticeProblemPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
