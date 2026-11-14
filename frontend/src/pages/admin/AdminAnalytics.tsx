import { useEffect, useState } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Cell,
} from "recharts"
import { BarChart3, TrendingUp, PieChart as PieIcon, RefreshCw, AlertCircle } from "lucide-react"
import { analyticsApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface TrendPoint {
  day: string
  discovered: number
}

interface CategoryPoint {
  name: string
  count: number
}

export function AdminAnalytics() {
  const [catData, setCatData] = useState<CategoryPoint[]>([])
  const [trendData, setTrendData] = useState<TrendPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAnalytics = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await analyticsApi.get()
      const labels: string[] = Array.isArray(res?.growth?.growth_labels) ? res.growth.growth_labels : []
      const values: number[] = Array.isArray(res?.growth?.growth_values) ? res.growth.growth_values : []
      setTrendData(labels.map((day, index) => ({ day, discovered: Number(values[index]) || 0 })))
      setCatData(
        Object.entries(res?.keywords ?? {}).map(([name, count]) => ({
          name,
          count: Number(count) || 0,
        }))
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analytics could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnalytics()
  }, [])

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Platform insights</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-cyber-blue" /> Discovery analytics
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Recent discovery activity and opportunity categories reported by the platform.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={loadAnalytics} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-cyber-blue" /> Recent discovery activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-72 animate-pulse rounded-md bg-muted/50" />
            ) : trendData.length === 0 ? (
              <p className="flex h-72 items-center justify-center text-sm text-muted-foreground">No discovery activity is available yet.</p>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey="day" stroke="#888888" fontSize={11} />
                    <YAxis stroke="#888888" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        borderColor: "hsl(var(--border))",
                        borderRadius: "0.5rem",
                        fontSize: "12px",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="discovered"
                      name="Discoveries"
                      stroke="hsl(221, 83%, 53%)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <PieIcon className="h-4 w-4 text-cyber-blue" /> Opportunities by Category
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-72 animate-pulse rounded-md bg-muted/50" />
            ) : catData.length === 0 ? (
              <p className="flex h-72 items-center justify-center text-sm text-muted-foreground">No category data is available yet.</p>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={catData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey="name" stroke="#888888" fontSize={10} interval={0} angle={-25} textAnchor="end" height={45} />
                    <YAxis stroke="#888888" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        borderColor: "hsl(var(--border))",
                        borderRadius: "0.5rem",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="count" name="Opportunities" fill="hsl(221, 83%, 53%)" radius={[4, 4, 0, 0]}>
                      {catData.map((entry, index) => (
                        <Cell key={`${entry.name}-${index}`} fill={`hsl(${221 + index * 17}, 70%, 52%)`} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

