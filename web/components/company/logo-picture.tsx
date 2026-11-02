import { Avatar } from "@/components/ui/avatar";

interface LogoPictureProps {
  name: string;
  hasLogo: boolean;
  size?: "md" | "lg";
  /** Change it to ask the browser for the picture again (after an upload or removal). */
  version?: number;
}

/**
 * The company's logo, or its initials on a soft colour. The picture comes from the API (signed-in
 * people only), so it is drawn from there with the session cookie rather than from a public address.
 */
export function LogoPicture({ name, hasLogo, size = "lg", version = 0 }: LogoPictureProps) {
  if (!hasLogo) return <Avatar name={name} size={size} decorative />;
  const base = process.env.NEXT_PUBLIC_API_URL ?? "";
  const box = size === "lg" ? "size-14" : "size-10";
  return (
    // The logo is a user's own upload from our API; the image component's optimiser cannot fetch it.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${base}/company/logo?v=${version}`}
      alt=""
      className={`${box} rounded-control bg-elevated shrink-0 object-contain`}
    />
  );
}
