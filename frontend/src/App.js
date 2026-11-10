import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp } from "@clerk/react";
import "@/App.css";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import { Toaster } from "@/components/ui/sonner";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import Workspace from "@/pages/Workspace";
import AuthShell from "@/pages/AuthShell";

const Protected = ({ children }) => (
  <>
    <Show when="signed-in">{children}</Show>
    <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
  </>
);

const Home = () => (
  <>
    <Show when="signed-in"><Navigate to="/dashboard" replace /></Show>
    <Show when="signed-out"><Landing /></Show>
  </>
);

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <ClerkAuthProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/sign-in/*" element={<AuthShell><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp /></AuthShell>} />
            <Route path="/sign-up/*" element={<AuthShell><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" /></AuthShell>} />
            <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
            <Route path="/p/:id" element={<Protected><Workspace /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ClerkAuthProvider>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}

export default App;
