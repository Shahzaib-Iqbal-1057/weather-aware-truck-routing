import { useId, useState, type KeyboardEvent } from 'react'
import { MIN_QUERY_LENGTH, usePlaceSearch } from '../../api/geocode'
import type { Place, PlaceKind } from '../../api/types'
import { useDebouncedValue } from '../../lib/useDebouncedValue'

const DEBOUNCE_MS = 300

const KIND_LABEL: Record<PlaceKind, string> = {
  city: 'City',
  address: 'Address',
  place: 'Place',
}

interface PlaceAutocompleteProps {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  error?: string
  placeholder?: string
}

/** Search-as-you-type for US places. The user must pick a suggestion, so we know exact coordinates. */
export function PlaceAutocomplete({
  label,
  value,
  onChange,
  error,
  placeholder,
}: PlaceAutocompleteProps) {
  const id = useId()
  const listId = `${id}-list`
  const errorId = `${id}-error`

  const [text, setText] = useState(value?.label ?? '')
  const [isOpen, setIsOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)

  const query = useDebouncedValue(text.trim(), DEBOUNCE_MS)
  const search = usePlaceSearch(query, value === null)
  const suggestions = search.data ?? []
  const showList = isOpen && value === null && text.trim().length >= MIN_QUERY_LENGTH

  function select(place: Place) {
    onChange(place)
    setText(place.label)
    setIsOpen(false)
  }

  function handleTextChange(next: string) {
    setText(next)
    setHighlighted(0)
    setIsOpen(true)
    if (value) onChange(null)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!showList) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((i) => Math.min(i + 1, suggestions.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && suggestions[highlighted]) {
      event.preventDefault()
      select(suggestions[highlighted])
    } else if (event.key === 'Escape') {
      setIsOpen(false)
    }
  }

  const optionId = (index: number) => `${id}-option-${index}`

  return (
    <div className="field place-autocomplete">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && suggestions.length ? optionId(highlighted) : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        placeholder={placeholder}
        value={text}
        onChange={(event) => handleTextChange(event.target.value)}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        onKeyDown={handleKeyDown}
      />
      {showList && (
        <ul id={listId} role="listbox" className="place-autocomplete__list">
          {suggestions.map((place, index) => (
            <li
              key={`${place.label}-${place.lat}-${place.lon}`}
              id={optionId(index)}
              role="option"
              aria-selected={index === highlighted}
              className="place-autocomplete__option"
              // mousedown (not click) so the input does not blur and close the list first
              onMouseDown={(event) => {
                event.preventDefault()
                select(place)
              }}
              onMouseEnter={() => setHighlighted(index)}
            >
              <span className="place-autocomplete__label">{place.label}</span>
              <span className="place-autocomplete__kind">{KIND_LABEL[place.kind]}</span>
            </li>
          ))}
          {suggestions.length === 0 && (
            <li className="place-autocomplete__status" role="presentation">
              {search.isError
                ? 'Location search is unavailable right now.'
                : search.isFetching || query !== text.trim()
                  ? 'Searching…'
                  : 'No US places found.'}
            </li>
          )}
        </ul>
      )}
      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
    </div>
  )
}
