import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Navbar from "./Navbar";

/** Everything inside requires sign-in; otherwise redirect to /login. */
export default function ProtectedRoute() {
  const { user, booting } = useAuth();
  const location = useLocation();

  if (booting) {
    return <div className="min-h-screen grid place-items-center"><span className="spinner" style={{ width: 28, height: 28 }} /></div>;
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  return (
    <>
      <Navbar />
      <main><Outlet /></main>
    </>
  );
}
