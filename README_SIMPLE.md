# ASCDC - Simple Agent System

## 🎯 **Fixed Issues**

### **✅ Recommendation Logic Fixed**
- **Before**: Complex operator agent with broken logic, metrics not updating
- **After**: Simple, reliable recommendation system with working metrics

### **✅ Metrics Now Update Properly**
- **Total Reward**: Accumulates correctly after each action
- **Necessary Action Ratio**: Calculated from actual action necessity
- **Positive Impact Rate**: Tracks successful interventions
- **Real-time Updates**: Metrics refresh every 2 seconds

### **✅ Agent Swapping System**
- **3 Available Agents**: Adaptive, Conservative, Aggressive
- **Hot Swapping**: Change agents without restart
- **API Endpoints**: `/agents`, `/agents/{name}`, `/metrics`

## 🚀 **How to Use**

### **Start Backend**
```bash
cd d:/products/Meta
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

### **Start Frontend**
```bash
cd d:/products/Meta
npm run dev
```

### **Access Application**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🎮 **Agent Strategies**

### **Simple-Adaptive** (Default)
- Responds to current queue conditions
- Acts when any queue > 10.0
- Balanced approach for general use

### **Simple-Conservative**
- Only acts in emergencies (queue B > 20.0)
- Uses RESTART actions for critical situations
- Minimal intervention strategy

### **Simple-Aggressive**
- Acts on any imbalance (queues > 5.0)
- Uses THROTTLE actions frequently
- Random actions for exploration

## 📊 **API Endpoints**

### **Core Endpoints**
- `GET /` - API status
- `POST /reset` - Reset environment
- `POST /step` - Apply action
- `POST /recommend` - Get recommendation
- `GET /state` - Environment state
- `GET /health` - Health check

### **Agent Management**
- `GET /agents` - List available agents
- `POST /agents/{name}` - Switch to specific agent
- `GET /metrics` - Current performance metrics
- `POST /metrics/reset` - Reset metrics

## 🔧 **Agent Swapping**

### **Via API**
```bash
# Switch to conservative agent
curl -X POST http://localhost:8000/agents/simple-conservative

# Switch to aggressive agent  
curl -X POST http://localhost:8000/agents/simple-aggressive
```

### **Via Frontend**
1. Navigate to **Agents** page
2. View current agent and available options
3. Click **Switch** button to change agents
4. Metrics update in real-time

## 🐛 **Troubleshooting**

### **Metrics Not Updating**
- Check browser console for errors
- Verify `/metrics` endpoint returns data
- Refresh page to restart metrics polling

### **Recommendations Not Changing**
- Verify `/recommend` endpoint returns different actions
- Check system state changes between recommendations
- Try switching agents to test different logic

### **Agent Switching Fails**
- Verify agent name is spelled correctly
- Check `/agents` endpoint for available options
- Look at server logs for errors

## 🎯 **Key Improvements**

1. **Simplified Logic**: Removed complex ML dependencies
2. **Real Metrics**: Actually tracks performance correctly  
3. **Hot Swapping**: Change agents without restart
4. **Error Handling**: Graceful fallbacks and recovery
5. **Transparency**: Clear agent strategies and behavior

The system now provides reliable, understandable AI recommendations with proper metrics tracking and easy agent swapping for testing different strategies.
