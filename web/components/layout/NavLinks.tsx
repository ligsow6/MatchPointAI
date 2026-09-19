"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAVIGATION } from "@/lib/site";
import styles from "./SiteHeader.module.css";

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLinks() {
  const pathname = usePathname();
  return (
    <ul className={styles.links}>
      {NAVIGATION.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              className={styles.link}
              aria-current={active ? "page" : undefined}
            >
              {item.label}
              {item.extra ? <span className={styles.extra}>{item.extra}</span> : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
