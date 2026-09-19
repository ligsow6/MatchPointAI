import Link from "next/link";
import { SITE_NAME } from "@/lib/site";
import { BrandMark } from "./BrandMark";
import { NavLinks } from "./NavLinks";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.header}>
      <div className={`container ${styles.inner}`}>
        <Link href="/" className={styles.brand}>
          <BrandMark />
          <span>{SITE_NAME}</span>
        </Link>
        <nav aria-label="Navigation principale" className={styles.nav}>
          <NavLinks />
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
