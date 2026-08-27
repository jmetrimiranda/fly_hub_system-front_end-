import { createBrowserRouter } from "react-router-dom";
import { AdminLayout } from "@/layouts/AdminLayout";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { FlightPage } from "@/pages/flight/FlightPage";
import { DatasetsPage } from "@/pages/datasets/DatasetsPage";
import { InspectionsPage } from "@/pages/inspections/InspectionsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AdminLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "voo", element: <FlightPage /> },
      { path: "datasets", element: <DatasetsPage /> },
      { path: "inspecao", element: <InspectionsPage /> },
    ],
  },
]);
