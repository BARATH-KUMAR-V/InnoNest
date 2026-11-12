import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { Login, Register } from "@/pages/Auth";
import Calculator from "@/pages/Calculator";
import ApplicationForm from "@/pages/portal/ApplicationForm";
import PortalApplicationDetail from "@/pages/portal/ApplicationDetail";
import Notifications from "@/pages/portal/Notifications";
import PortalHome from "@/pages/portal/PortalHome";
import Audit from "@/pages/workspace/Audit";
import Dashboard from "@/pages/workspace/Dashboard";
import FollowUp from "@/pages/workspace/FollowUp";
import Integrations from "@/pages/workspace/Integrations";
import Policies from "@/pages/workspace/Policies";
import Register_ from "@/pages/workspace/Register";
import WorkspaceApplicationDetail from "@/pages/workspace/ApplicationDetail";
import NotFound from "@/pages/NotFound";

function homeFor(role: Role) {
  return role === "applicant" ? "/portal" : "/workspace";
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

function Guard({ area }: { area: "applicant" | "staff" }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><Spinner /></div>;
  if (!user) return <Navigate to="/login" replace />;
  const isApplicant = user.role === "applicant";
  if ((area === "applicant") !== isApplicant) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

function Public() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><Spinner /></div>;
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route element={<Public />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>
      <Route element={<Guard area="applicant" />}>
        <Route element={<Layout />}>
          <Route path="/portal" element={<PortalHome />} />
          <Route path="/portal/applications/new" element={<ApplicationForm />} />
          <Route path="/portal/applications/:id" element={<PortalApplicationDetail />} />
          <Route path="/portal/applications/:id/edit" element={<ApplicationForm />} />
          <Route path="/portal/notifications" element={<Notifications />} />
          <Route path="/portal/calculator" element={<Calculator />} />
        </Route>
      </Route>
      <Route element={<Guard area="staff" />}>
        <Route element={<Layout />}>
          <Route path="/workspace" element={<Dashboard />} />
          <Route path="/workspace/applications" element={<Register_ />} />
          <Route path="/workspace/applications/:id" element={<WorkspaceApplicationDetail />} />
          <Route path="/workspace/follow-up" element={<FollowUp />} />
          <Route path="/workspace/policies" element={<Policies />} />
          <Route path="/workspace/integrations" element={<Integrations />} />
          <Route path="/workspace/audit" element={<Audit />} />
          <Route path="/workspace/calculator" element={<Calculator />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
