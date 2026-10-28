using System;
using System.Collections.Generic;
using System.Configuration;
using System.Data.SqlClient;

namespace Contoso.Billing.Data
{
    public class CustomerRepository
    {
        private readonly string _connectionString =
            ConfigurationManager.ConnectionStrings["BillingDb"].ConnectionString;

        public List<Customer> GetCustomersByCity(string city)
        {
            var customers = new List<Customer>();
            using (var connection = new SqlConnection(_connectionString))
            {
                var command = new SqlCommand("SELECT Id, Name, City FROM Customers WHERE City = '" + city + "'", connection);
                connection.Open();
                using (var reader = command.ExecuteReader())
                {
                    while (reader.Read())
                    {
                        customers.Add(new Customer
                        {
                            Id = reader.GetInt32(0),
                            Name = reader.GetString(1),
                            City = reader.GetString(2)
                        });
                    }
                }
            }
            return customers;
        }

        public void DeleteCustomer(int customerId)
        {
            using (var connection = new SqlConnection(_connectionString))
            {
                var command = new SqlCommand("DELETE FROM Customers WHERE Id = " + customerId, connection);
                connection.Open();
                command.ExecuteNonQuery();
            }
        }
    }

    public class Customer
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string City { get; set; }
    }
}
