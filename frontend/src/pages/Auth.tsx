import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { brand } from "@/lib/brand";

const demoAccounts = [
  { label: "Applicant", email: "applicant@example.com", password: "Applicant@123" },
  { label: "Underwriter", email: "underwriter@example.com", password: "Underwriter@123" },
  { label: "Policy admin", email: "policy@example.com", password: "PolicyAdmin@123" },
  { label: "Auditor", email: "auditor@example.com", password: "Auditor@123" },
];

const points = ["One application, connected evidence, an explainable decision", "Missing documents lead to a clear checklist, not a rejection", "Every outcome ships with its policy, version and reasons"];

function Frame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="hidden flex-col justify-between bg-brand px-12 py-12 text-white lg:flex">
        <Logo light />
        <div>
          <h2 className="max-w-md font-display text-4xl font-extrabold leading-tight">{brand.tagline}</h2>
          <p className="mt-4 max-w-md text-[#C9DDCF]">{brand.identity}. Home Loan and Loan Against Property underwriting that explains itself.</p>
          <ul className="mt-8 space-y-3">
            {points.map((point) => (
              <li key={point} className="flex items-start gap-3 text-sm text-[#E3EEE6]">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#9FCBAE]" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-[#9FBBA9]">Demonstration build. Lender policies are illustrative and integrations are simulated.</p>
      </div>
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <Logo />
            <p className="mt-2 text-sm text-muted">{brand.tagline}</p>
          </div>
          <h1 className="page-title">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}

function home(role: string) {
  return role === "applicant" ? "/portal" : "/workspace";
}

const loginSchema = z.object({ email: z.string().email("Enter a valid email address"), password: z.string().min(1, "Enter your password") });

export function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  if (user) return <Navigate to={home(user.role)} replace />;

  const submit = form.handleSubmit(async (values) => {
    try {
      const signedIn = await signIn(values.email, values.password);
      navigate(home(signedIn.role), { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });

  return (
    <Frame title={`Sign in to ${brand.name}`} subtitle="Use your applicant or lender account.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Email" error={form.formState.errors.email?.message}>
          <Input type="email" autoComplete="username" {...form.register("email")} />
        </Field>
        <Field label="Password" error={form.formState.errors.password?.message}>
          <Input type="password" autoComplete="current-password" {...form.register("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        New to {brand.name}?{" "}
        <Link to="/register" className="font-medium text-brand underline">
          Create an applicant account
        </Link>
      </p>
      <div className="mt-8 rounded-lg border border-line bg-white p-4">
        <p className="label-sm">Demo accounts</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {demoAccounts.map((account) => (
            <Button
              key={account.email}
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                form.setValue("email", account.email);
                form.setValue("password", account.password);
              }}
            >
              {account.label}
            </Button>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">These accounts are created for local use only. Change or remove them before any real deployment.</p>
      </div>
    </Frame>
  );
}

const registerSchema = z.object({
  full_name: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email address"),
  phone: z.string().regex(/^([6-9][0-9]{9})?$/, "Enter a 10 digit mobile number").optional(),
  password: z.string().min(8, "Use at least 8 characters"),
});

export function Register() {
  const { user, register: signUp } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const form = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema), defaultValues: { full_name: "", email: "", phone: "", password: "" } });
  if (user) return <Navigate to={home(user.role)} replace />;

  const submit = form.handleSubmit(async (values) => {
    try {
      await signUp({ ...values, phone: values.phone || undefined });
      toast.success(`Welcome to ${brand.name}`);
      navigate("/portal", { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });

  return (
    <Frame title={`Create your ${brand.name} account`} subtitle="Start a Home Loan or LAP application and track it here.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Full name" error={form.formState.errors.full_name?.message}>
          <Input autoComplete="name" {...form.register("full_name")} />
        </Field>
        <Field label="Email" error={form.formState.errors.email?.message}>
          <Input type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label="Mobile number (optional)" error={form.formState.errors.phone?.message}>
          <Input inputMode="numeric" maxLength={10} {...form.register("phone")} />
        </Field>
        <Field label="Password" error={form.formState.errors.password?.message} hint="At least 8 characters">
          <Input type="password" autoComplete="new-password" {...form.register("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already registered?{" "}
        <Link to="/login" className="font-medium text-brand underline">
          Sign in
        </Link>
      </p>
    </Frame>
  );
}
