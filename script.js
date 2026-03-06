// Sample data for charts
const salesData = {
    labels: ["January", "February", "March", "April", "May", "June"],
    datasets: [{
        label: "Sales ($)",
        data: [1200, 1900, 3000, 2500, 3200, 4000],
        backgroundColor: "rgba(74,144,226,0.5)",
        borderColor: "rgba(74,144,226,1)",
        borderWidth: 2,
        fill: true,
        tension: 0.3
    }]
};

const categoryData = {
    labels: ["Electronics", "Clothing", "Grocery", "Cosmetics", "Beverages"],
    datasets: [{
        label: "Category Sales",
        data: [5000, 3000, 4000, 2000, 1500],
        backgroundColor: [
            "rgba(255, 99, 132, 0.7)",
            "rgba(54, 162, 235, 0.7)",
            "rgba(255, 206, 86, 0.7)",
            "rgba(75, 192, 192, 0.7)",
            "rgba(153, 102, 255, 0.7)"
        ],
        borderColor: "white",
        borderWidth: 1
    }]
};

// Initialize Sales Line Chart
const ctxSales = document.getElementById("salesChart").getContext("2d");
new Chart(ctxSales, {
    type: "line",
    data: salesData,
    options: {
        responsive: true,
        plugins: {
            legend: { position: "top" },
            title: { display: true, text: "Monthly Sales Overview" }
        }
    }
});

// Initialize Category Pie Chart
const ctxCategory = document.getElementById("categoryChart").getContext("2d");
new Chart(ctxCategory, {
    type: "pie",
    data: categoryData,
    options: {
        responsive: true,
        plugins: {
            legend: { position: "bottom" },
            title: { display: true, text: "Sales by Category" }
        }
    }
});
