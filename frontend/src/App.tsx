import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Employers from "./pages/Employers";
import JobDetail from "./pages/JobDetail";
import Pipeline from "./pages/Pipeline";
import Outbox from "./pages/Outbox";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";
import ResumeReview from "./pages/ResumeReview";
import Shortlist from "./pages/Shortlist";
import TailoredResume from "./pages/TailoredResume";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Pipeline />} />
        <Route path="shortlist" element={<Shortlist />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="jobs/:id/resume" element={<TailoredResume />} />
        <Route path="resumes" element={<ResumeReview />} />
        <Route path="outbox" element={<Outbox />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<Profile />} />
        <Route path="employers" element={<Employers />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
