// Copyright 2018 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// Modified by the Antojo project, 2026

package main

import (
	"fmt"
	"math"
)

const (
	// DeliveryCurrency is the currency of every delivery fee quote.
	DeliveryCurrency = "MXN"
	// DeliveryFeeMXN is the flat delivery fee for an order.
	DeliveryFeeMXN = 35.0
	// FreeDeliveryMinItems is the item count at which delivery becomes free.
	// GetQuoteRequest carries items but no prices, so the threshold is
	// expressed in items to keep the gRPC contract unchanged.
	FreeDeliveryMinItems = 6
	// MinETAMinutes and MaxETAMinutes bound the estimated delivery time.
	MinETAMinutes = 25
	MaxETAMinutes = 45
)

// Quote represents a delivery fee in MXN.
type Quote struct {
	Units uint32
	Cents uint32
}

// String representation of the Quote.
func (q Quote) String() string {
	return fmt.Sprintf("$%d.%02d %s", q.Units, q.Cents, DeliveryCurrency)
}

// CreateQuoteFromCount takes a number of items and returns a delivery fee
// quote: zero for an empty order, free from FreeDeliveryMinItems items,
// otherwise the flat DeliveryFeeMXN.
func CreateQuoteFromCount(count int) Quote {
	if count == 0 || count >= FreeDeliveryMinItems {
		return CreateQuoteFromFloat(0)
	}
	return CreateQuoteFromFloat(DeliveryFeeMXN)
}

// EstimateETAMinutes returns the delivery time window in minutes. Larger
// orders take longer to prepare, capped at MaxETAMinutes.
func EstimateETAMinutes(count int) (int, int) {
	high := MinETAMinutes + 10 + 2*count
	if high > MaxETAMinutes {
		high = MaxETAMinutes
	}
	return MinETAMinutes, high
}

// CreateQuoteFromFloat takes a price represented as a float and creates a Quote.
func CreateQuoteFromFloat(value float64) Quote {
	units, fraction := math.Modf(value)
	return Quote{
		uint32(units),
		uint32(math.Round(fraction * 100)),
	}
}
