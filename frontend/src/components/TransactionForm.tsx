import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import type { FundListItem } from '../api/funds'
import type { Holding, ManualFund, Transaction } from '../api/portfolio'
import { useDebounced } from '../hooks/useDebounced'
import { useFunds } from '../hooks/useFunds'
import { useGoals } from '../hooks/useGoals'
import { useAddManualFund, useAddSip, useAddTransaction, useManualFunds, useUpdateTransaction } from '../hooks/usePortfolio'
import { apiErrorMessage } from '../lib/apiError'
import { formatDate, formatNav, optionLabel, planLabel } from '../lib/format'
import { withoutGrouping } from '../lib/money'
import { FormError, SelectField, SubmitButton, TextField } from './form'

const today = () => new Date().toISOString().slice(0, 10)

/** Empty box → undefined; otherwise a number (amount boxes may hold "12,34,567"). */
const optionalNumber = (raw: unknown) => {
  const value = withoutGrouping(raw)
  return value === '' || value == null ? undefined : Number(value)
}

// Same rules as TransactionCreate / SipCreate in backend/app/schemas/portfolio.py.
const schema = z
  .object({
    kind: z.enum(['buy', 'sell', 'sip']),
    goal: z.string(), // '0' = not assigned to a goal
    holding: z.string(), // for a new redemption: the holding's id
    date: z.string().min(1, 'Choose a date'),
    end_date: z.string(),
    amount: z.preprocess(optionalNumber, z.number({ error: 'Enter an amount' }).positive('Must be more than 0').optional()),
    units: z.preprocess(optionalNumber, z.number({ error: 'Enter the units' }).positive('Must be more than 0').optional()),
    redeem_all: z.boolean(),
    own_nav: z.boolean(), // the NAV comes from the user (their statement), not the database
    nav: z.preprocess(optionalNumber, z.number({ error: 'Enter the NAV' }).positive('Must be more than 0').optional()),
  })
  .superRefine((v, ctx) => {
    if (v.date > today()) ctx.addIssue({ code: 'custom', path: ['date'], message: 'Cannot be in the future' })
    if (v.kind !== 'sell' && v.amount === undefined)
      ctx.addIssue({ code: 'custom', path: ['amount'], message: 'Enter the amount invested' })
    if (v.kind === 'sell' && !v.redeem_all && v.amount === undefined && v.units === undefined)
      ctx.addIssue({ code: 'custom', path: ['amount'], message: 'Enter the amount or the units' })
    if (v.kind === 'sip' && v.end_date && v.end_date < v.date)
      ctx.addIssue({ code: 'custom', path: ['end_date'], message: 'Must be after the first instalment' })
    if (v.own_nav && v.kind !== 'sip' && v.nav === undefined)
      ctx.addIssue({ code: 'custom', path: ['nav'], message: 'Enter the NAV' })
  })

type FormInput = z.input<typeof schema>
type FormValues = z.output<typeof schema>

/** A fund chosen in the picker: from AMFI's list, or one the user added (no market NAV). */
interface PickedFund {
  id: number
  name: string
  detail: string
  manual: boolean
}

const fromList = (f: FundListItem): PickedFund => ({
  id: f.id,
  name: f.name,
  manual: false,
  detail: `${f.category} · ${planLabel[f.plan]} · ${optionLabel[f.option]}${
    f.latest_nav !== null && f.latest_nav_date ? ` · NAV ${formatNav(f.latest_nav)} on ${formatDate(f.latest_nav_date)}` : ''
  }`,
})

const fromManual = (f: ManualFund): PickedFund => ({ id: f.id, name: f.name, manual: true, detail: f.category })

const kindOptions = [
  { value: 'buy', label: 'Purchase (lump sum)' },
  { value: 'sip', label: 'Monthly SIP (past instalments)' },
  { value: 'sell', label: 'Redemption' },
]

/**
 * Record a purchase, a SIP's past instalments, or a redemption of a holding; or, with `editing`,
 * correct a recorded purchase or redemption.
 */
export function TransactionForm({
  holdings,
  goalId,
  editing,
  onSaved,
}: {
  holdings: Holding[]
  goalId?: number
  editing?: Transaction
  onSaved: () => void
}) {
  const goals = useGoals()
  const addTransaction = useAddTransaction()
  const updateTransaction = useUpdateTransaction()
  const addSip = useAddSip()
  const [fund, setFund] = useState<PickedFund | null>(
    editing ? { id: editing.fund_id, name: editing.fund_name, manual: editing.manual_fund, detail: '' } : null,
  )
  const [serverError, setServerError] = useState<string | null>(null)
  const open = holdings.filter((h) => h.units > 0)

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(schema),
    defaultValues: editing
      ? {
          // A correction keeps the recorded NAV unless the user changes or unticks it.
          kind: editing.txn_type,
          goal: editing.goal_id ? String(editing.goal_id) : '0',
          holding: '',
          date: editing.txn_date,
          end_date: '',
          amount: String(editing.amount),
          units: '',
          redeem_all: false,
          own_nav: true,
          nav: String(editing.nav),
        }
      : {
          kind: 'buy',
          goal: goalId ? String(goalId) : '0',
          holding: '',
          date: today(),
          end_date: '',
          amount: '',
          units: '',
          redeem_all: false,
          own_nav: false,
          nav: '',
        },
  })
  const kind = useWatch({ control, name: 'kind' })
  const redeemAll = useWatch({ control, name: 'redeem_all' })
  const holdingId = useWatch({ control, name: 'holding' })
  const ownNavTicked = useWatch({ control, name: 'own_nav' })
  const selected = open.find((h) => String(h.id) === holdingId)
  // A new redemption picks a holding; everything else (and every correction) picks a fund.
  const fromHolding = kind === 'sell' && !editing
  const manual = fromHolding ? (selected?.manual ?? false) : (fund?.manual ?? false)
  const ownNav = manual || ownNavTicked // a fund the user added has no NAVs in the database

  const goalOptions = [
    { value: '0', label: 'Not assigned to a goal' },
    ...(goals.data ?? []).map((g) => ({ value: String(g.id), label: g.name })),
  ]

  const onSubmit = async (v: FormValues) => {
    setServerError(null)
    const goal_id = v.goal && v.goal !== '0' ? Number(v.goal) : null
    if (ownNav && v.kind !== 'sip' && v.nav === undefined) {
      setServerError('Enter the NAV: GoalWise has no prices for funds you add yourself')
      return
    }
    const nav = ownNav && v.nav !== undefined ? { nav: v.nav } : {}
    try {
      if (fromHolding) {
        const h = selected
        if (!h) {
          setServerError('Choose what to redeem')
          return
        }
        await addTransaction.mutateAsync({
          fund_id: h.fund_id,
          goal_id: h.goal_id,
          txn_type: 'sell',
          txn_date: v.date,
          ...(v.redeem_all ? { units: h.units } : { amount: v.amount, units: v.units }),
          ...nav,
        })
      } else if (!fund) {
        setServerError('Choose a fund')
        return
      } else if (v.kind === 'sip') {
        if (fund.manual) {
          setServerError('For a fund you added, record each instalment as a purchase with its NAV')
          return
        }
        await addSip.mutateAsync({
          fund_id: fund.id,
          goal_id,
          amount: v.amount!,
          start_date: v.date,
          ...(v.end_date ? { end_date: v.end_date } : {}),
        })
      } else {
        const input = {
          fund_id: fund.id,
          goal_id,
          txn_type: v.kind,
          txn_date: v.date,
          amount: v.amount,
          ...(v.kind === 'sell' && v.units !== undefined ? { units: v.units } : {}),
          ...nav,
          ...(editing?.note ? { note: editing.note } : {}), // a corrected SIP instalment stays a SIP
        }
        if (editing) await updateTransaction.mutateAsync({ id: editing.id, input })
        else await addTransaction.mutateAsync(input)
      }
      onSaved()
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="max-w-xl space-y-4">
      <FormError message={serverError} />
      <SelectField
        label="Type"
        options={editing ? kindOptions.filter((o) => o.value !== 'sip') : kindOptions}
        registration={register('kind')}
      />

      {fromHolding ? (
        <SelectField
          label="Redeem from"
          options={open.map((h) => ({
            value: String(h.id),
            label: `${h.fund_name} · ${h.goal_name ?? 'Not assigned'} · ${h.units.toLocaleString('en-IN')} units`,
          }))}
          registration={register('holding')}
          error={errors.holding?.message}
          hint={open.length === 0 ? 'Nothing to redeem yet.' : undefined}
        />
      ) : (
        <>
          <FundPicker fund={fund} onChange={setFund} />
          <SelectField label="For goal" options={goalOptions} registration={register('goal')} />
        </>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label={kind === 'sip' ? 'First instalment' : 'Date'}
          type="date"
          max={today()}
          registration={register('date')}
          error={errors.date?.message}
          hint={kind === 'sip' ? 'Then the same day every month' : ownNav ? undefined : 'The NAV of that day is used'}
        />
        {kind === 'sip' && (
          <TextField
            label="Last instalment (optional)"
            type="date"
            max={today()}
            registration={register('end_date')}
            error={errors.end_date?.message}
            hint="Empty: up to today"
          />
        )}
      </div>

      {fromHolding && (
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" {...register('redeem_all')} className="h-4 w-4 rounded border-slate-300 text-emerald-600" />
          Redeem everything{selected ? ` (${selected.units.toLocaleString('en-IN')} units)` : ''}
        </label>
      )}
      {!(fromHolding && redeemAll) && (
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={kind === 'sip' ? 'Amount each month' : kind === 'sell' ? 'Amount redeemed' : 'Amount invested'}
            prefix="₹"
            registration={register('amount')}
            error={errors.amount?.message}
            hint={kind === 'buy' ? 'Units are worked out from the NAV, after 0.005% stamp duty' : undefined}
          />
          {kind === 'sell' && (
            <TextField
              label="Or units redeemed"
              type="number"
              inputMode="decimal"
              step="0.001"
              registration={register('units')}
              error={errors.units?.message}
            />
          )}
        </div>
      )}

      {kind !== 'sip' && (
        <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              {...register('own_nav')}
              checked={ownNav}
              disabled={manual}
              className="h-4 w-4 rounded border-slate-300 text-emerald-600 disabled:opacity-60"
            />
            Enter the NAV myself (from my statement)
          </label>
          <p className="text-xs text-slate-500">
            {manual
              ? 'GoalWise has no prices for a fund you added, so its NAV is needed. Its holdings are valued at cost.'
              : ownNav
                ? 'Useful for old transactions, or when your statement shows a different NAV.'
                : "Unticked: GoalWise uses the fund's NAV of that day (or the last one in the week before)."}
          </p>
          {ownNav && (
            <TextField
              label="NAV (₹ per unit)"
              type="number"
              inputMode="decimal"
              step="0.0001"
              registration={register('nav')}
              error={errors.nav?.message}
            />
          )}
        </div>
      )}

      <SubmitButton busy={isSubmitting}>
        {editing ? 'Save changes' : kind === 'sip' ? 'Add instalments' : 'Add transaction'}
      </SubmitButton>
    </form>
  )
}

const assetClassOptions = [
  { value: 'equity', label: 'Equity' },
  { value: 'debt', label: 'Debt' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'other', label: 'Other' },
]

/** Search the fund list (and the user's own funds) by name, or add a fund that is not listed. */
function FundPicker({ fund, onChange }: { fund: PickedFund | null; onChange: (fund: PickedFund | null) => void }) {
  const [search, setSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const q = useDebounced(search.trim(), 300)
  const results = useFunds({ q, sort: 'name', order: 'asc', page: 1, page_size: 8 })
  const mine = useManualFunds()
  const myMatches = (mine.data ?? []).filter((f) => q.length >= 3 && f.name.toLowerCase().includes(q.toLowerCase()))

  if (fund) {
    return (
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-700">Fund</p>
        <div className="flex items-start justify-between gap-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2">
          <div>
            <p className="text-sm font-medium">{fund.name}</p>
            {(fund.detail || fund.manual) && (
              <p className="text-xs text-slate-600">{fund.manual ? 'Added by you · valued at cost' : fund.detail}</p>
            )}
          </div>
          <button type="button" onClick={() => onChange(null)} className="text-sm font-medium text-emerald-700 hover:underline">
            Change
          </button>
        </div>
      </div>
    )
  }
  if (adding) {
    return <AddOwnFund initialName={search.trim()} onCancel={() => setAdding(false)} onAdded={(f) => onChange(fromManual(f))} />
  }
  return (
    <div className="space-y-1">
      <label htmlFor="fund-search" className="block text-sm font-medium text-slate-700">
        Fund
      </label>
      <input
        id="fund-search"
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by fund name, e.g. parag parikh flexi"
        className="block w-full rounded-md border border-slate-300 px-3 py-2 shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
      />
      {q.length >= 3 && (
        <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200 bg-white" aria-label="Matching funds">
          {myMatches.map((f) => (
            <li key={`mine-${f.id}`}>
              <button type="button" onClick={() => onChange(fromManual(f))} className="w-full px-3 py-2 text-left hover:bg-emerald-50">
                <span className="block text-sm">{f.name}</span>
                <span className="block text-xs text-slate-500">Added by you · {f.category}</span>
              </button>
            </li>
          ))}
          {results.data?.items.map((f) => (
            <li key={f.id}>
              <button type="button" onClick={() => onChange(fromList(f))} className="w-full px-3 py-2 text-left hover:bg-emerald-50">
                <span className="block text-sm">{f.name}</span>
                <span className="block text-xs text-slate-500">
                  {f.category} · {planLabel[f.plan]} · {optionLabel[f.option]}
                  {f.latest_nav !== null && ` · ${formatNav(f.latest_nav)}`}
                </span>
              </button>
            </li>
          ))}
          {results.data?.items.length === 0 && myMatches.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500">No fund matches “{q}”.</li>
          )}
        </ul>
      )}
      {q.length < 3 && <p className="text-sm text-slate-500">Type at least 3 letters.</p>}
      {results.data && results.data.total > 8 && q.length >= 3 && (
        <p className="text-xs text-slate-500">Showing 8 of {results.data.total.toLocaleString('en-IN')} matches; type more to narrow down.</p>
      )}
      <button type="button" onClick={() => setAdding(true)} className="text-sm font-medium text-emerald-700 hover:underline">
        Can&apos;t find it? Add it yourself
      </button>
    </div>
  )
}

/** A fund that is not in the list: a name and its type. Its NAVs come from the user. */
function AddOwnFund({
  initialName,
  onCancel,
  onAdded,
}: {
  initialName: string
  onCancel: () => void
  onAdded: (fund: ManualFund) => void
}) {
  const add = useAddManualFund()
  const [name, setName] = useState(initialName)
  const [assetClass, setAssetClass] = useState<ManualFund['asset_class']>('equity')
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (name.trim().length < 2) {
      setError('Give the fund a name')
      return
    }
    setError(null)
    try {
      onAdded(await add.mutateAsync({ name: name.trim(), asset_class: assetClass }))
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-medium text-slate-700">Add a fund that is not in the list</p>
      <FormError message={error} />
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <label className="block space-y-1 text-sm">
          <span className="text-slate-700">Fund name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            className="block w-full rounded-md border border-slate-300 px-3 py-2 shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="text-slate-700">Type</span>
          <select
            value={assetClass}
            onChange={(e) => setAssetClass(e.target.value as ManualFund['asset_class'])}
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          >
            {assetClassOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-xs text-slate-500">
        GoalWise has no prices for it: you enter the NAV of each transaction, and it is valued at what you paid.
      </p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={add.isPending}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          {add.isPending ? 'Adding…' : 'Add fund'}
        </button>
        <button type="button" onClick={onCancel} className="text-sm font-medium text-slate-600 hover:underline">
          Back to search
        </button>
      </div>
    </div>
  )
}
