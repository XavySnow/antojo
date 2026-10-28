# Shipping Service

The shipping service quotes the MXN delivery fee and issues ANT- tracking IDs for Antojo orders.

## Local

Run the following command to restore dependencies to `vendor/` directory:

    dep ensure --vendor-only

## Build

From `services/shippingservice`, run:

```
docker build ./
```

## Test

```
go test .
```
