import { redirect } from "next/navigation";
import { headers } from "next/headers";

import MaryLandingSplash from "@/components/MaryLandingSplash";
import { auth } from "@/lib/auth";

export default async function HomePage() {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (session?.user) redirect("/dashboard");

  return <MaryLandingSplash />;
}
