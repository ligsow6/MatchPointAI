"use client";

import { useId, useState, type KeyboardEvent } from "react";
import { searchPlayers, type SearchIndex } from "@/lib/comparator/players";
import type { PlayerRecord } from "@/lib/comparator/types";
import { formatInteger } from "@/lib/format";
import styles from "./Comparator.module.css";

type PlayerComboboxProps = {
  label: string;
  index: SearchIndex | null;
  selected: PlayerRecord | null;
  onSelect: (player: PlayerRecord | null) => void;
  swatch: string;
};

function describe(player: PlayerRecord): string {
  const year = player.lastMatch.slice(0, 4);
  const country = player.country ? `${player.country} · ` : "";
  return `${country}${formatInteger(player.played)} matchs · dernier en ${year}`;
}

export function PlayerCombobox({ label, index, selected, onSelect, swatch }: PlayerComboboxProps) {
  const inputId = useId();
  const listId = useId();
  const hintId = useId();
  const [query, setQuery] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [previousSelection, setPreviousSelection] = useState(selected);

  if (previousSelection !== selected) {
    setPreviousSelection(selected);
    setQuery(selected?.name ?? "");
  }

  const results = index && open ? searchPlayers(index, query) : [];
  const expanded = open && results.length > 0;
  const optionId = (position: number) => `${listId}-option-${position}`;

  const choose = (player: PlayerRecord) => {
    setQuery(player.name);
    setOpen(false);
    setActive(-1);
    onSelect(player);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((current) => (results.length === 0 ? -1 : (current + 1) % results.length));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActive((current) =>
        results.length === 0 ? -1 : (current - 1 + results.length) % results.length,
      );
    } else if (event.key === "Enter" && expanded) {
      event.preventDefault();
      const player = results[active >= 0 ? active : 0];
      if (player) {
        choose(player);
      }
    } else if (event.key === "Escape") {
      if (expanded) {
        event.preventDefault();
        setOpen(false);
        setActive(-1);
      } else if (query) {
        event.preventDefault();
        setQuery("");
        onSelect(null);
      }
    }
  };

  return (
    <div className={styles.combobox}>
      <label htmlFor={inputId} className={styles.fieldLabel}>
        <span className={styles.swatch} style={{ background: swatch }} aria-hidden="true" />
        {label}
      </label>
      <div className={styles.inputWrapper}>
        <input
          id={inputId}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          placeholder={index ? "Tapez un nom, ex. Nadal" : "Chargement des joueurs…"}
          disabled={!index}
          value={query}
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-describedby={hintId}
          aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={handleKeyDown}
          className={styles.input}
        />
        {query ? (
          <button
            type="button"
            className={styles.clear}
            onClick={() => {
              setQuery("");
              onSelect(null);
            }}
            aria-label={`Effacer ${label.toLowerCase()}`}
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </div>
      <p id={hintId} className="visually-hidden">
        Flèches haut et bas pour parcourir les suggestions, Entrée pour choisir, Échap pour fermer.
      </p>
      <ul
        id={listId}
        role="listbox"
        aria-label={`Suggestions pour ${label.toLowerCase()}`}
        className={styles.listbox}
        hidden={!expanded}
      >
        {results.map((player, position) => (
          <li
            key={player.id}
            id={optionId(position)}
            role="option"
            aria-selected={position === active}
            className={styles.option}
            onMouseDown={(event) => {
              event.preventDefault();
              choose(player);
            }}
            onMouseEnter={() => setActive(position)}
          >
            <span className={styles.optionName}>{player.name}</span>
            <span className={styles.optionMeta}>{describe(player)}</span>
          </li>
        ))}
      </ul>
      {open && index && query.trim() && results.length === 0 ? (
        <p className={styles.noResult}>Aucun joueur trouvé.</p>
      ) : null}
    </div>
  );
}
