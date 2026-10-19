import { BackendStatus } from './components/BackendStatus'
import './App.css'

export default function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>Weather-Aware Truck Routing</h1>
        <BackendStatus />
      </header>
      <main className="app__main">
        <p className="placeholder">Trip form (Stage 0) goes here.</p>
      </main>
    </div>
  )
}
