import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Pipeline from "./pages/Pipeline";
import Shortlist from "./pages/Shortlist";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Pipeline />} />
        <Route path="shortlist" element={<Shortlist />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
