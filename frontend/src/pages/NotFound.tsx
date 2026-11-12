import { Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { useTitle } from "@/hooks/useTitle";

export default function NotFound() {
  useTitle("Page not found");
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <Logo />
      <h1 className="page-title">We could not find that page</h1>
      <p className="max-w-sm text-sm text-muted">The address may be wrong, or the page may have moved.</p>
      <Button asChild><Link to="/">Back to start</Link></Button>
    </div>
  );
}
