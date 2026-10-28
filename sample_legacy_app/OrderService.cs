using System;
using System.Data.SqlClient;
using System.ServiceModel;
using System.Web;
using Contoso.Billing.Data;

namespace Contoso.Billing.Services
{
    [ServiceContract]
    public interface IOrderService
    {
        [OperationContract]
        decimal GetOutstandingBalance(int customerId);

        [OperationContract]
        void CloseAccount(int customerId);
    }

    public class OrderService : IOrderService
    {
        private const string ConnectionString =
            "Server=billing-db;Database=Billing;User Id=billing_app;Password=Billing@2015;";

        private readonly CustomerRepository _customers = new CustomerRepository();

        public decimal GetOutstandingBalance(int customerId)
        {
            var requestedBy = HttpContext.Current.User.Identity.Name;
            System.Diagnostics.Trace.WriteLine("Balance requested by " + requestedBy);

            using (var connection = new SqlConnection(ConnectionString))
            {
                var command = new SqlCommand(
                    "SELECT SUM(Amount) FROM Invoices WHERE Paid = 0 AND CustomerId = @customerId", connection);
                command.Parameters.AddWithValue("@customerId", customerId);
                connection.Open();
                var result = command.ExecuteScalar();
                return result == DBNull.Value ? 0 : (decimal)result;
            }
        }

        public void CloseAccount(int customerId)
        {
            _customers.DeleteCustomer(customerId);
        }
    }
}
