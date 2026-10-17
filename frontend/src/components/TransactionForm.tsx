import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import type { FundListItem } from '../api/funds'
import type { Holding } from '../api/portfolio'
import { useDebounced } from '../hooks/useDebounced'
import { useFunds } from '../hooks/useFunds'
import { useGoals } from '../hooks/useGoals'
import { useAddSip, useAddTransaction } from '../hooks/usePortfolio'
import { apiErrorMessage } from '../lib/apiError'
import { formatDate, formatNav, optionLabel, planLabel } from '../lib/format'
import { FormError, SelectField, SubmitButton, TextField } from './form'

const today = () => new Date().toISOString().slice(0, 10)

/** Empty box → undefined; otherwise a number. */
const optionalNumber = (value: unknown) => (value === '' || value == null ? undefined : Number(value))

// Same rules as TransactionCreate / SipCreate in backend/app/schemas/portfolio.py.
const schema = z
  .object({
    kind: z.enum(['buy', 'sell', 'sip']),
    goal: z.string(), // '0' = not assigned to a goal
    holding: z.string(), // for a redemption: the holding's id
    date: z.string().min(1, 'Choose a date'),
    end_date: z.string(),
    amount: z.preprocess(optionalNumber, z.number({ error: 'Enter an amount' }).positive('Must be more than 0').optional()),
    units: z.preprocess(optionalNumber, z.number({ error: 'Enter the units' }).positive('Must be more than 0').optional()),
    redeem_all: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.date > today()) ctx.addIssue({ code: 'custom', path: ['date'], message: 'Cannot be in the future' })
    if (v.kind !== 'sell' && v.amount === undefined)
      ctx.addIssue({ code: 'custom', path: ['amount'], message: 'Enter the amount invested' })
    if (v.kind === 'sell') {
      if (!v.holding) ctx.addIssue({ code: 'custom', path: ['holding'], message: 'Choose what to redeem' })
      if (!v.redeem_all && v.amount === undefined && v.units === undefined)
        ctx.addIssue({ code: 'custom', path: ['amount'], message: 'Enter the amount or the units' })
    }
    if (v.kind === 'sip' && v.end_date && v.end_date < v.date)
      ctx.addIssue({ code: 'custom', path: ['end_date'], message: 'Must be after the first instalment' })
  })

type FormInput = z.input<typeof schema>
type FormValues = z.output<typeof schema>

const kindOptions = [
  { value: 'buy', label: 'Purchase (lump sum)' },
  { value: 'sip', label: 'Monthly SIP (past instalments)' },
  { value: 'sell', label: 'Redemption' },
]

/** Record a purchase, a SIP's past instalments, or a redemption of a holding. */
export function TransactionForm({
  holdings,
  goalId,
  onSaved,
}: {
  holdings: Holding[]
  goalId?: number
  onSaved: () => void
}) {
  const goals = useGoals()
  const addTransaction = useAddTransaction()
  const addSip = useAddSip()
  const [fund, setFund] = useState<FundListItem | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const open = holdings.filter((h) => h.units > 0)

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      kind: 'buy',
      goal: goalId ? String(goalId) : '0',
      holding: '',
      date: today(),
      end_date: '',
      amount: '',
      units: '',
      redeem_all: false,
    },
  })
  const kind = useWatch({ control, name: 'kind' })
  const redeemAll = useWatch({ control, name: 'redeem_all' })
  const holdingId = useWatch({ control, name: 'holding' })
  const selected = open.find((h) => String(h.id) === holdingId)

  const goalOptions = [
    { value: '0', label: 'Not assigned to a goal' },
    ...(goals.data ?? []).map((g) => ({ value: String(g.id), label: g.name })),
  ]

  const onSubmit = async (v: FormValues) => {
    setServerError(null)
    const goal_id = v.goal && v.goal !== '0' ? Number(v.goal) : null
    try {
      if (v.kind === 'sell') {
        const h = selected!
        await addTransaction.mutateAsync({
          fund_id: h.fund_id,
          goal_id: h.goal_id,
          txn_type: 'sell',
          txn_date: v.date,
          ...(v.redeem_all ? { units: h.units } : { amount: v.amount, units: v.units }),
        })
      } else if (!fund) {
        setServerError('Choose a fund')
        return
      } else if (v.kind === 'sip') {
        await addSip.mutateAsync({
          fund_id: fund.id,
          goal_id,
          amount: v.amount!,
          start_date: v.date,
          ...(v.end_date ? { end_date: v.end_date } : {}),
        })
      } else {
        await addTransaction.mutateAsync({ fund_id: fund.id, goal_id, txn_type: 'buy', txn_date: v.date, amount: v.amount })
      }
      onSaved()
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="max-w-xl space-y-4">
      <FormError message={serverError} />
      <SelectField label="Type" options={kindOptions} registration={register('kind')} />

      {kind === 'sell' ? (
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
          hint={kind === 'sip' ? 'Then the same day every month' : 'The NAV of that day is used'}
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

      {kind === 'sell' && (
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" {...register('redeem_all')} className="h-4 w-4 rounded border-slate-300 text-emerald-600" />
          Redeem everything{selected ? ` (${selected.units.toLocaleString('en-IN')} units)` : ''}
        </label>
      )}
      {!(kind === 'sell' && redeemAll) && (
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={kind === 'sip' ? 'Amount each month' : kind === 'sell' ? 'Amount redeemed' : 'Amount invested'}
            type="number"
            inputMode="decimal"
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

      <SubmitButton busy={isSubmitting}>{kind === 'sip' ? 'Add instalments' : 'Add transaction'}</SubmitButton>
    </form>
  )
}

/** Search the fund list by name and pick one. */
function FundPicker({ fund, onChange }: { fund: FundListItem | null; onChange: (fund: FundListItem | null) => void }) {
  const [search, setSearch] = useState('')
  const q = useDebounced(search.trim(), 300)
  const results = useFunds({ q, sort: 'name', order: 'asc', page: 1, page_size: 8 })

  if (fund) {
    return (
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-700">Fund</p>
        <div className="flex items-start justify-between gap-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2">
          <div>
            <p className="text-sm font-medium">{fund.name}</p>
            <p className="text-xs text-slate-600">
              {fund.category} · {planLabel[fund.plan]} · {optionLabel[fund.option]}
              {fund.latest_nav !== null && fund.latest_nav_date && ` · NAV ${formatNav(fund.latest_nav)} on ${formatDate(fund.latest_nav_date)}`}
            </p>
          </div>
          <button type="button" onClick={() => onChange(null)} className="text-sm font-medium text-emerald-700 hover:underline">
            Change
          </button>
        </div>
      </div>
    )
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
          {results.data?.items.map((f) => (
            <li key={f.id}>
              <button type="button" onClick={() => onChange(f)} className="w-full px-3 py-2 text-left hover:bg-emerald-50">
                <span className="block text-sm">{f.name}</span>
                <span className="block text-xs text-slate-500">
                  {f.category} · {planLabel[f.plan]} · {optionLabel[f.option]}
                  {f.latest_nav !== null && ` · ${formatNav(f.latest_nav)}`}
                </span>
              </button>
            </li>
          ))}
          {results.data?.items.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No fund matches “{q}”.</li>}
        </ul>
      )}
      {q.length < 3 && <p className="text-sm text-slate-500">Type at least 3 letters.</p>}
      {results.data && results.data.total > 8 && q.length >= 3 && (
        <p className="text-xs text-slate-500">Showing 8 of {results.data.total.toLocaleString('en-IN')} matches; type more to narrow down.</p>
      )}
    </div>
  )
}
