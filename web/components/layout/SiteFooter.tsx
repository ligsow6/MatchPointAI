import { REPOSITORY_URL, SITE_NAME } from "@/lib/site";
import styles from "./SiteFooter.module.css";

type SiteFooterProps = {
  dataThrough: string;
};

export function SiteFooter({ dataThrough }: SiteFooterProps) {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.inner}`}>
        <p className={styles.brand}>{SITE_NAME}</p>
        <p>
          Données :{" "}
          <a href="https://github.com/JeffSackmann" rel="noopener">
            Jeff Sackmann / Tennis Abstract
          </a>{" "}
          (résultats ATP et Match Charting Project), sous licence{" "}
          <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr" rel="noopener">
            CC BY-NC-SA 4.0
          </a>
          . Matchs jusqu&apos;au {dataThrough}.
        </p>
        <p>
          Projet personnel, non commercial, sans lien avec l&apos;ATP ni avec un site de paris.{" "}
          <a href={REPOSITORY_URL} rel="noopener">
            Code source
          </a>
          .
        </p>
      </div>
    </footer>
  );
}
