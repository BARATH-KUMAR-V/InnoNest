import { useEffect } from "react";
import { brand } from "@/lib/brand";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | ${brand.name}`;
  }, [title]);
}
